"""
Description:
Stałe scenariuszy „pytań już nie trzeba”: plik zestawu i klucz metryczki.
"""

from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
QUESTIONS_FILE = Path("data/safe/golden/questions.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"
