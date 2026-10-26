"""Teste simple pentru logica aplicației AI Report Assistant."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app  # noqa: E402

SAMPLE_PATH = PROJECT_ROOT / "sample_report.csv"
APP_PATH = PROJECT_ROOT / "app.py"


class LoadCsvTests(unittest.TestCase):
    def test_sample_file_loads(self):
        df = app.load_csv(SAMPLE_PATH)

        self.assertEqual(df.shape, (12, 5))
        self.assertEqual(
            app.find_numeric_columns(df),
            ["unitati_vandute", "venit_ron", "cost_ron"],
        )

    def test_empty_file_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "gol"):
            app.load_csv(io.StringIO(""))

    def test_header_only_file_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "rânduri de date"):
            app.load_csv(io.StringIO("a,b\n"))

    def test_columns_without_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "fără nume"):
            app.load_csv(io.StringIO("nume,,valoare\nA,1,10\n"))

    def test_file_like_source_is_supported(self):
        df = app.load_csv(io.StringIO("nume,valoare\nA,10\nB,20\n"))

        self.assertEqual(df["valoare"].sum(), 30)

    def test_semicolon_separated_file_loads(self):
        df = app.load_csv(io.StringIO("nume;valoare\nA;10\nB;20\n"))

        self.assertEqual(list(df.columns), ["nume", "valoare"])
        self.assertEqual(app.find_numeric_columns(df), ["valoare"])

    def test_missing_file_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "nu a putut fi citit"):
            app.load_csv(PROJECT_ROOT / "nu_exista.csv")

    def test_non_utf8_file_has_clear_error(self):
        invalid_utf8 = io.BytesIO(b"nume,valoare\nA,\xff\n")

        with self.assertRaisesRegex(ValueError, "UTF-8"):
            app.load_csv(invalid_utf8)


class NumericAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "nume": ["A", "B", "C"],
                "valoare": [10, 20, 30],
                "cost": [1.5, 2.5, None],
                "text_numeric": ["10", "20", "30"],
                "gol": [None, None, None],
            }
        )

    def test_only_real_numeric_columns_are_selected(self):
        self.assertEqual(app.find_numeric_columns(self.df), ["valoare", "cost"])

    def test_sum_mean_and_missing_values(self):
        stats = app.column_stats(self.df, ["valoare", "cost"]).set_index("Coloană")

        self.assertEqual(stats.loc["valoare", "Sumă"], 60)
        self.assertEqual(stats.loc["valoare", "Medie"], 20)
        self.assertEqual(stats.loc["valoare", "Minim"], 10)
        self.assertEqual(stats.loc["valoare", "Mediană"], 20)
        self.assertEqual(stats.loc["valoare", "Maxim"], 30)
        self.assertEqual(stats.loc["valoare", "Valori lipsă"], 0)
        self.assertEqual(stats.loc["cost", "Sumă"], 4)
        self.assertEqual(stats.loc["cost", "Medie"], 2)
        self.assertEqual(stats.loc["cost", "Minim"], 1.5)
        self.assertEqual(stats.loc["cost", "Mediană"], 2)
        self.assertEqual(stats.loc["cost", "Maxim"], 2.5)
        self.assertEqual(stats.loc["cost", "Valori lipsă"], 1)

    def test_summary_contains_dataset_shape_and_statistics(self):
        summary = app.build_summary(self.df, ["valoare", "cost"])

        self.assertIn("3 rânduri", summary)
        self.assertIn("5 coloane", summary)
        self.assertIn("`valoare`", summary)
        self.assertIn("sumă 60,00", summary)
        self.assertIn("medie 20,00", summary)
        self.assertIn("minim 10,00", summary)
        self.assertIn("mediană 20,00", summary)
        self.assertIn("maxim 30,00", summary)

    def test_summary_without_numeric_columns(self):
        df = pd.DataFrame({"nume": ["A", "B"], "oraș": ["X", "Y"]})

        self.assertEqual(app.find_numeric_columns(df), [])
        self.assertIn(
            "Nu au fost găsite coloane numerice",
            app.build_summary(df, []),
        )

    def test_numeric_strings_are_not_treated_as_numbers(self):
        df = app.load_csv(io.StringIO("valoare\n10\ntext\n30\n"))

        self.assertEqual(app.find_numeric_columns(df), [])


class LlmTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "client": ["Nume Confidențial", "Client B", "Client C"],
                "valoare": [10, 20, 30],
            }
        )

    def test_prompt_contains_statistics_but_not_raw_values(self):
        prompt = app.build_llm_prompt(self.df, ["valoare"])

        self.assertIn("valoare", prompt)
        self.assertIn("sumă=60", prompt)
        self.assertIn("client", prompt)
        self.assertNotIn("Nume Confidențial", prompt)

    def test_generate_ai_summary_calls_openai_client(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Rezumat AI."))]
        )

        with patch("openai.OpenAI") as client_class:
            client_class.return_value.chat.completions.create.return_value = response
            summary = app.generate_ai_summary(
                "prompt de test",
                {"api_key": "test-key", "model": "test-model"},
            )

        self.assertEqual(summary, "Rezumat AI.")
        client_class.assert_called_once_with(api_key="test-key")
        request = client_class.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["messages"][1]["content"], "prompt de test")

    def test_empty_ai_response_has_clear_error(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="   "))]
        )

        with patch("openai.OpenAI") as client_class:
            client_class.return_value.chat.completions.create.return_value = response
            with self.assertRaisesRegex(ValueError, "răspuns gol"):
                app.generate_ai_summary("prompt", {"api_key": "test-key"})


class AppSmokeTests(unittest.TestCase):
    def test_app_loads_demo_data_without_exceptions(self):
        app_test = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

        self.assertEqual(len(app_test.exception), 0)
        self.assertEqual(len(app_test.metric), 3)
        self.assertEqual(len(app_test.dataframe), 2)
        self.assertEqual(len(app_test.selectbox), 1)
        self.assertEqual(
            app_test.selectbox[0].options,
            ["unitati_vandute", "venit_ron", "cost_ron"],
        )
        self.assertEqual(app_test.radio[0].options, ["Bare", "Linii"])
        self.assertEqual(len(app_test.download_button), 1)

    def test_app_asks_for_input_when_demo_is_disabled(self):
        app_test = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        app_test.checkbox[0].uncheck().run()

        self.assertEqual(len(app_test.exception), 0)
        self.assertEqual(len(app_test.info), 1)


if __name__ == "__main__":
    unittest.main()
