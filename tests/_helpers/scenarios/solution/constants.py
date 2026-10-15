"""
Description:
Stałe scenariuszy rozwiązania: plik zestawu, klucz metryczki i fragmenty treści, w których znak
zapytania nie jest pytaniem do klienta.
"""

import re
from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
SOLUTION_FILE = Path("data/safe/golden/solution.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"

# Fragmenty treści dla klienta, w których znak zapytania nie jest pytaniem: cytat w polskim
# cudzysłowie (komunikat z ekranu, „Czy zapisać zmiany?”) i adres z parametrami. Licznik pytań
# wycina je przed liczeniem.
NOT_A_QUESTION = re.compile(r"„[^”]*”|https?://\S+")
