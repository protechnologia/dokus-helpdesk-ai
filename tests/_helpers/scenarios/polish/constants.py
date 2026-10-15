"""
Description:
Stałe scenariuszy „Popraw”: plik zestawu, klucz metryczki i reguły porównania tekstu.
"""

import re
from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
POLISH_FILE = Path("data/safe/golden/polish.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"

# Zamiana liter, których rozkład Unicode nie zdejmuje do litery bez znaku. Bez niej „łapie”
# w poprawionym tekście nie znalazłoby „lapie” z notatek pisanych bez polskich znaków.
EXTRA_LETTERS = str.maketrans({
    "ł": "l",
})

# Numer listy na początku linii („1. ”, „12) ”), który ocena usuwa przed liczeniem liczb: zasady
# stylu każą numerować kroki, więc numer kroku nie jest dopisaną liczbą.
LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
