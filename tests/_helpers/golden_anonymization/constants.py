"""
Description:
Stałe golden setu anonimizatora: pliki zestawów, rodzaje danych i wiedzy oraz reguły porównania
słów.
"""

import re
from pathlib import Path

# Zestaw zmyślony, w repo: pilnuje oceny i zjawisk, których w próbce korpusu może zabraknąć.
# Ścieżka od korzenia repo, bo z niego uruchamia się pytest.
SAFE_FILE = Path("data/safe/golden/anonymization.json")

# Próbka korpusu: prawdziwe wątki z danymi klientów, poza repo.
UNSAFE_FILE = Path("data/unsafe/golden/anonymization.json")

# Rodzaje danych, które mają zniknąć. Nazwy to nazwy znaczników z p. 19, bez nawiasów; znacznika
# w wyniku ocena nie sprawdza, a rodzaj służy do liczenia przecieków osobno. `DOKUMENT` to numer
# dowodu osobistego albo paszportu.
REMOVE_KINDS = (
    "IMIĘ",
    "NAZWISKO",
    "PESEL",
    "NIP",
    "REGON",
    "KONTO",
    "DOKUMENT",
    "TELEFON",
    "EMAIL",
    "ADRES",
)

# Rodzaje wiedzy, która ma zostać. `NUMER` to liczba, która nie jest daną osobową, także
# w kształcie danej (numer zgłoszenia, przesyłki, liczba bez poprawnej sumy kontrolnej), a `SŁOWO`
# to słowo albo nazwa, które wyglądają jak dana (pułapka).
KEEP_KINDS = (
    "KOD_BŁĘDU",
    "KOMUNIKAT",
    "WERSJA",
    "USŁUGA",
    "NUMER",
    "SŁOWO",
)

# Słowo w ocenie: ciąg liter i cyfr. Interpunkcja, odstępy i znaki nowej linii słów nie tworzą,
# więc fragment „Anna Wiśniewska” znajduje imię i nazwisko w dwóch liniach podpisu,
# a „600 123 456” — „600-123-456”.
WORD = re.compile(r"[^\W_]+")

# Zamiana liter, których rozkład Unicode nie zdejmuje do litery bez znaku. Bez niej nazwisko
# „Michał” wypisane przez silnik jako „Michal” nie liczyłoby się jako przeciek.
EXTRA_LETTERS = str.maketrans({
    "ł": "l",
})
