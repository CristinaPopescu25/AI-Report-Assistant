"""AI Report Assistant: analiză locală a unui fișier CSV, cu rezumat AI opțional."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DEMO_PATH = Path(__file__).with_name("sample_report.csv")
DEFAULT_LLM_MODEL = "gpt-4o-mini"


def _read_sample(source, size: int = 4096) -> str:
    """Read a small text sample so the CSV separator can be detected."""
    if hasattr(source, "read"):
        original_position = source.tell() if hasattr(source, "tell") else 0
        sample = source.read(size)
        if hasattr(source, "seek"):
            source.seek(original_position)
    else:
        with open(source, "r", encoding="utf-8-sig", errors="replace") as file:
            sample = file.read(size)

    if isinstance(sample, bytes):
        return sample.decode("utf-8-sig", errors="replace")
    return sample


def detect_separator(sample: str) -> str:
    """Use a comma or a semicolon based on the CSV header."""
    header = next((line for line in sample.splitlines() if line.strip()), "")
    return ";" if header.count(";") > header.count(",") else ","


def _has_missing_name(column_name: str) -> bool:
    """Return True for empty or auto-generated pandas column names."""
    clean_name = column_name.strip()
    return not clean_name or clean_name.lower().startswith("unnamed:")


def load_csv(source) -> pd.DataFrame:
    """Read a comma- or semicolon-separated CSV and validate its structure."""
    try:
        separator = detect_separator(_read_sample(source))
        df = pd.read_csv(source, sep=separator, encoding="utf-8-sig")
    except pd.errors.EmptyDataError as exc:
        raise ValueError("Fișierul este gol sau nu conține nicio coloană.") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(
            "Fișierul nu are un format CSV valid. "
            "Verifică separatorul (virgulă sau punct-virgulă) și ghilimelele."
        ) from exc
    except UnicodeDecodeError as exc:
        raise ValueError(
            "Fișierul nu este text UTF-8. Salvează-l ca CSV UTF-8 și încearcă din nou."
        ) from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"Fișierul nu a putut fi citit: {exc}") from exc

    if df.columns.empty:
        raise ValueError("Fișierul nu conține nicio coloană.")
    if df.empty:
        raise ValueError("Fișierul nu conține rânduri de date (doar antetul).")
    if any(_has_missing_name(str(column)) for column in df.columns):
        raise ValueError(
            "Fișierul are coloane fără nume. Adaugă un antet pentru fiecare coloană."
        )

    return df


def find_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric columns that contain at least one value."""
    return [
        column
        for column in df.columns
        if pd.api.types.is_numeric_dtype(df[column])
        and not pd.api.types.is_bool_dtype(df[column])
        and df[column].notna().any()
    ]


def column_stats(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Build a table with statistics for the given numeric columns."""
    return pd.DataFrame(
        {
            "Coloană": columns,
            "Sumă": [df[column].sum() for column in columns],
            "Medie": [df[column].mean() for column in columns],
            "Minim": [df[column].min() for column in columns],
            "Mediană": [df[column].median() for column in columns],
            "Maxim": [df[column].max() for column in columns],
            "Valori lipsă": [int(df[column].isna().sum()) for column in columns],
        }
    )


def format_number(value: float) -> str:
    """Format a number using Romanian separators, or a fallback for NaN."""
    if pd.isna(value):
        return "indisponibil"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_summary(df: pd.DataFrame, numeric_columns: list[str]) -> str:
    """Create a rule-based summary of the dataset, without an AI service."""
    row_count, column_count = df.shape
    lines = [
        f"Setul de date conține **{row_count} rânduri** și **{column_count} coloane**."
    ]

    if not numeric_columns:
        lines.append(
            "Nu au fost găsite coloane numerice, deci nu se pot calcula sume sau medii."
        )
        return "\n\n".join(lines)

    stats = column_stats(df, numeric_columns)
    lines.append(
        f"Au fost identificate **{len(numeric_columns)} coloane numerice**: "
        + ", ".join(f"`{column}`" for column in numeric_columns)
        + "."
    )

    for _, row in stats.iterrows():
        lines.append(
            f"- **{row['Coloană']}**: sumă {format_number(row['Sumă'])}, "
            f"medie {format_number(row['Medie'])}, "
            f"minim {format_number(row['Minim'])}, "
            f"mediană {format_number(row['Mediană'])}, "
            f"maxim {format_number(row['Maxim'])}, "
            f"valori lipsă {int(row['Valori lipsă'])}."
        )

    top_column = stats.loc[stats["Sumă"].idxmax()]
    lines.append(
        f"Coloana cu cea mai mare sumă este **{top_column['Coloană']}** "
        f"({format_number(top_column['Sumă'])})."
    )

    return "\n\n".join(lines)


def get_llm_config() -> dict[str, str]:
    """Read optional LLM settings from Streamlit secrets."""
    try:
        if "llm" not in st.secrets:
            return {}
        llm_settings = st.secrets["llm"]
    except Exception:
        return {}

    api_key = str(llm_settings.get("api_key", "")).strip()
    if not api_key:
        return {}

    config = {
        "api_key": api_key,
        "model": str(llm_settings.get("model", DEFAULT_LLM_MODEL)).strip()
        or DEFAULT_LLM_MODEL,
    }
    base_url = str(llm_settings.get("base_url", "")).strip()
    if base_url:
        config["base_url"] = base_url
    return config


def build_llm_prompt(df: pd.DataFrame, numeric_columns: list[str]) -> str:
    """Build a prompt with aggregate statistics only, without raw data rows."""
    stats = column_stats(df, numeric_columns)
    if stats.empty:
        statistics_text = "- Nu există coloane numerice."
    else:
        statistics_text = "\n".join(
            f"- {row['Coloană']}: sumă={row['Sumă']}, medie={row['Medie']}, "
            f"minim={row['Minim']}, mediană={row['Mediană']}, maxim={row['Maxim']}, "
            f"valori lipsă={row['Valori lipsă']}"
            for _, row in stats.iterrows()
        )

    column_names = ", ".join(str(column) for column in df.columns)
    numeric_names = ", ".join(numeric_columns) or "niciuna"
    text_columns = [
        str(column) for column in df.columns if column not in numeric_columns
    ]

    return (
        "Analizează statisticile de mai jos și scrie un rezumat clar pentru un "
        "raport de business, în limba română, de maximum 150 de cuvinte. "
        "Menționează dimensiunea setului de date, cele mai relevante coloane "
        "numerice și una sau două observații practice. Nu inventa valori și "
        "folosește doar statisticile furnizate.\n\n"
        f"Rânduri: {df.shape[0]}\n"
        f"Coloane: {df.shape[1]}\n"
        f"Numele coloanelor: {column_names}\n"
        f"Coloane numerice: {numeric_names}\n"
        f"Coloane text: {', '.join(text_columns) or 'niciuna'}\n"
        "Statistici numerice:\n"
        f"{statistics_text}"
    )


def generate_ai_summary(prompt: str, config: dict[str, str]) -> str:
    """Generate a summary with an OpenAI-compatible chat completion API."""
    from openai import OpenAI

    client_options = {"api_key": config["api_key"]}
    if config.get("base_url"):
        client_options["base_url"] = config["base_url"]

    client = OpenAI(**client_options)
    response = client.chat.completions.create(
        model=config.get("model", DEFAULT_LLM_MODEL),
        messages=[
            {
                "role": "system",
                "content": (
                    "Ești un analist de date riguros. Răspunde doar pe baza "
                    "statisticilor primite și nu inventa valori."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("Furnizorul AI a returnat un răspuns gol.")
    return content.strip()


def render_llm_summary(
    df: pd.DataFrame,
    numeric_columns: list[str],
    llm_config: dict[str, str],
    context_key: str,
) -> None:
    """Show the optional AI summary and keep its result per loaded dataset."""
    st.subheader("Rezumat AI (opțional)")
    if not llm_config:
        st.caption(
            "Rezumatul AI este dezactivat. Adaugă cheia API în "
            "`.streamlit/secrets.toml` pentru a-l activa; rezumatul pe bază "
            "de reguli rămâne disponibil."
        )
        return

    st.caption(
        "Se trimit către furnizorul AI doar statistici agregate și numele "
        "coloanelor, nu rândurile brute."
    )
    if st.button("Generează rezumatul AI"):
        with st.spinner("Se generează rezumatul AI..."):
            try:
                summary = generate_ai_summary(
                    build_llm_prompt(df, numeric_columns),
                    llm_config,
                )
            except Exception as exc:
                st.session_state.pop("ai_summary", None)
                st.session_state.pop("ai_summary_key", None)
                st.error(f"Rezumatul AI nu a putut fi generat: {exc}")
            else:
                st.session_state["ai_summary"] = summary
                st.session_state["ai_summary_key"] = context_key

    if (
        st.session_state.get("ai_summary_key") == context_key
        and st.session_state.get("ai_summary")
    ):
        st.markdown(st.session_state["ai_summary"])


def render_summary(
    df: pd.DataFrame,
    numeric_columns: list[str],
    source_name: str,
    llm_config: dict[str, str],
) -> None:
    """Show the rule-based summary, its download, and the optional AI summary."""
    summary = build_summary(df, numeric_columns)
    st.subheader("Rezumat automat")
    st.markdown(summary)
    st.download_button(
        "Descarcă rezumatul (Markdown)",
        data=summary,
        file_name=f"rezumat_{Path(source_name).stem}.md",
        mime="text/markdown",
    )

    context_key = (
        f"{source_name}|{df.shape[0]}|{df.shape[1]}|"
        f"{','.join(map(str, numeric_columns))}"
    )
    render_llm_summary(df, numeric_columns, llm_config, context_key)


def main() -> None:
    st.set_page_config(
        page_title="AI Report Assistant",
        page_icon="📊",
        layout="wide",
    )

    st.title("AI Report Assistant")
    st.caption(
        "Analizează local un fișier CSV. Rezumatul AI este opțional și "
        "trimite doar statistici agregate."
    )

    uploaded_file = st.file_uploader("Încarcă un fișier CSV", type=["csv"])
    use_demo = st.checkbox(
        "Folosește fișierul demonstrativ",
        value=uploaded_file is None,
        help="Încarcă sample_report.csv, ca să poți testa aplicația fără date proprii.",
    )

    if uploaded_file is not None:
        source = uploaded_file
        source_name = uploaded_file.name
    elif use_demo:
        if not DEMO_PATH.exists():
            st.error("Fișierul demonstrativ sample_report.csv lipsește din proiect.")
            return
        source = DEMO_PATH
        source_name = DEMO_PATH.name
    else:
        st.info(
            "Încarcă un fișier CSV sau bifează opțiunea pentru datele demonstrative."
        )
        return

    try:
        df = load_csv(source)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.success(f"Fișier încărcat: **{source_name}**")

    llm_config = get_llm_config()
    numeric_columns = find_numeric_columns(df)
    row_count, column_count = df.shape

    rows_metric, columns_metric, numeric_metric = st.columns(3)
    rows_metric.metric("Rânduri", row_count)
    columns_metric.metric("Coloane", column_count)
    numeric_metric.metric("Coloane numerice", len(numeric_columns))

    st.subheader("Previzualizare date")
    st.dataframe(df, width="stretch")

    ignored_columns = [
        column for column in df.columns if column not in numeric_columns
    ]
    if ignored_columns:
        st.caption(
            "Coloane neincluse în statistici: "
            + ", ".join(f"`{column}`" for column in ignored_columns)
            + "."
        )

    if not numeric_columns:
        st.warning(
            "Fișierul nu conține coloane numerice. "
            "Sumele, mediile și graficul nu pot fi calculate."
        )
        render_summary(df, numeric_columns, source_name, llm_config)
        return

    st.subheader("Statistici pentru coloanele numerice")
    st.dataframe(
        column_stats(df, numeric_columns),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Analiză pe o coloană")
    selected_column = st.selectbox(
        "Alege o coloană numerică",
        options=numeric_columns,
    )
    chart_type = st.radio(
        "Tip grafic",
        options=["Bare", "Linii"],
        horizontal=True,
    )
    chart_data = (
        df[selected_column].dropna().reset_index(drop=True).to_frame(name=selected_column)
    )
    if chart_type == "Linii":
        st.line_chart(chart_data, y=selected_column, height=320)
    else:
        st.bar_chart(chart_data, y=selected_column, height=320)

    render_summary(df, numeric_columns, source_name, llm_config)


if __name__ == "__main__":
    main()
