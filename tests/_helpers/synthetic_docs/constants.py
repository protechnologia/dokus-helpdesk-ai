"""
Description:
Stałe dokumentacji syntetycznej: paczka, zestaw zapytań, podpowiedź budowy indeksu i progi pomiaru
wyszukiwania po znaczeniu.
"""

from pathlib import Path

# Paczka dokumentacji syntetycznej: katalog na dokument, w nim plik `.md` na sekcję. Ścieżka od
# korzenia repo, bo z niego uruchamia się pytest.
PACKAGE_DIR = Path("data/safe/instruction")

# Zestaw zapytań do paczki, sekcja na narzędzie, ze spisem sekcji w kolejności dokumentów.
GOLDEN_FILE = Path("data/safe/golden/docs-synthetic.json")

# Podpowiedź do błędu pomiaru, gdy indeksu syntetycznego nie ma albo nie odpowiada paczce: pomiar
# kończy się błędem z poleceniem, które indeks buduje.
BUILD_HINT = (
    "zbuduj indeks syntetyczny: "
    "docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes"
)

# Próg: zapytania, na które oczekiwana sekcja wraca pierwsza. Zmierzone 24 z 24; próg niżej, żeby
# wyłapać zepsutą ścieżkę, a nie zwykły dryf.
MIN_EXPECTED_FIRST = 22

# Próg: dystraktory niżej niż oczekiwana sekcja. Zmierzone 9 z 9. Dystraktor to sekcja o tym samym
# zagadnieniu w innym kanale — postawiony wyżej odwraca radę.
MIN_DISTRACTORS_BELOW = 8

# Próg: zapytania bez odpowiedzi, na które wraca choć jedna sekcja. Zmierzone 1 z 5: jedno
# zapytanie dostaje dwie sekcje tuż nad progiem.
MAX_UNANSWERED_WITH_HITS = 2
