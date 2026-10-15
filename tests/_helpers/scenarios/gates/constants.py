"""
Description:
Stałe scenariuszy bramek: plik zestawu, klucz metryczki i rodzaje spraw.
"""

from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
GATES_FILE = Path("data/safe/golden/gates.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnej bramki.
META_KEY = "meta"

# Werdykt, którego wymaga każdy rodzaj sprawy: po nim ocena rozpoznaje fałszywy alarm
# i przepuszczenie, a test zestawu sprawdza, czy rodzaj sprawy jest znany.
EXPECTED_VERDICTS = {
    "breaks":  "block",
    "correct": "pass",
    "trap":    "pass",
}

# Nazwa rodzaju sprawy w raporcie, po polsku, żeby raport czytało się bez zestawu obok.
KIND_LABELS = {
    "breaks":  "łamie",
    "correct": "poprawna",
    "trap":    "pułapka",
}
