# AI Report Assistant

O aplicație web locală, construită cu **Python**, **Streamlit** și **pandas**, care
analizează un fișier CSV și generează automat un rezumat pe bază de reguli.

Aplicația este prima versiune funcțională: **nu folosește un LLM, un API AI sau
servicii cloud**. Toate datele rămân pe calculatorul local.

## Funcționalități

- încărcarea unui fișier CSV cu separator virgulă sau punct-virgulă;
- previzualizarea datelor într-un tabel;
- afișarea numărului de rânduri și coloane;
- detectarea automată a coloanelor numerice, fără a presupune numele acestora;
- calcularea sumei, mediei, minimului, medianei, maximului și numărului de
  valori lipsă pentru fiecare coloană numerică;
- selectarea unei coloane numerice și afișarea graficului cu bare sau cu linii;
- generarea și descărcarea rezumatului automat, ca fișier Markdown;
- mesaje clare pentru fișiere goale, invalide, fără antet sau fără date numerice;
- fișier demonstrativ inclus: `sample_report.csv` (date fictive).

## Structura proiectului

```text
.
├── app.py               # aplicația Streamlit și logica de analiză
├── requirements.txt     # dependențele, cu versiuni fixate
├── sample_report.csv    # date demonstrative fictive
├── tests/
│   └── test_app.py      # teste pentru logică și pentru pornirea aplicației
├── .gitignore
└── README.md
```

## Instalare pe Windows

Deschide **PowerShell** în folderul proiectului:

```powershell
cd "C:\Users\crist\Documents\Default Project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Dacă PowerShell blochează activarea mediului virtual, folosește direct
executabilul din `.venv`, fără activare:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Pornire

Cu mediul virtual activat:

```powershell
python -m streamlit run app.py
```

Sau fără activare:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Deschide în browser adresa afișată în terminal:

```text
http://localhost:8501
```

## Utilizare

1. La prima deschidere, opțiunea **Folosește fișierul demonstrativ** este bifată,
   deci aplicația afișează imediat datele din `sample_report.csv`.
2. Pentru date proprii, încarcă un fișier CSV în zona de upload. Fișierul încărcat
   are prioritate față de datele demonstrative.
3. Verifică tabelul, statisticile și rezumatul generat automat.
4. Alege o coloană numerică din lista **Alege o coloană numerică** și tipul de
   grafic (**Bare** sau **Linii**).
5. Folosește butonul **Descarcă rezumatul (Markdown)** pentru a salva rezumatul
   generat.

Pentru a opri aplicația, apasă `Ctrl+C` în terminal.

## Cerințe pentru fișierul CSV

- prima linie trebuie să conțină numele coloanelor;
- separatorul poate fi virgula sau punctul-virgulă și este detectat automat;
- codificarea recomandată este UTF-8;
- coloanele numerice trebuie să conțină numere simple (de exemplu `1250` sau
  `1250.50`, cu punct zecimal);
- coloanele text sunt afișate, dar nu sunt incluse în sume, medii sau grafic.

Aplicația nu presupune nume de coloane. Detectează automat coloanele numerice.

**Limitare cunoscută:** valorile cu virgulă zecimală (de exemplu `1250,50`) nu
sunt convertite automat în numere în această versiune. Folosește punctul zecimal
sau înlocuiește virgula zecimală înainte de upload.

## Testare

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testele verifică încărcarea CSV-ului demonstrativ, separatoarele virgulă și
punct-virgulă, validările, calculele statistice, rezumatul generat, prezența
butonului de descărcare și pornirea aplicației cu datele demo.

## Depanare

- **Portul 8501 este ocupat**: pornește aplicația pe alt port:

  ```powershell
  python -m streamlit run app.py --server.port 8502
  ```

  Apoi deschide `http://localhost:8502`.

- **Fișierul nu este citit**: verifică faptul că este un CSV cu separator virgulă
  sau punct-virgulă, cu antet și codificare UTF-8.
- **Nu apar coloane numerice**: verifică dacă valorile sunt numere, nu text
  (de exemplu `"10"` cu ghilimele sau `1.250,50` pot fi interpretate ca text).

## Limitări intenționate în această versiune

- fără integrare LLM sau API AI;
- fără baze de date, Docker sau servicii cloud;
- fără autentificare sau publicare online;
- două tipuri de grafic (bare și linii), generate cu componentele incluse în
  Streamlit.

Următoarea etapă poate adăuga un rezumat asistat de LLM, păstrând analiza de bază
funcțională local.
