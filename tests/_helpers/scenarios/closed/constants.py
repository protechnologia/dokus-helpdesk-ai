"""
Description:
Stałe scenariuszy trasy zamknięcia zgłoszenia: plik zestawu i wyniki spraw.
"""

from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
CLOSED_FILE = Path("data/safe/golden/closed.json")

# Wynik, którego sprawa może wymagać; te same wartości oddaje trasa w polu `outcome`.
EXPECTED_OUTCOMES = ("blocked", "indexed", "dropped")

# Nazwa wyniku w raporcie, po polsku, żeby raport czytało się bez zestawu obok.
OUTCOME_LABELS = {
    "blocked": "zablokowane",
    "indexed": "do indeksów",
    "dropped": "odrzucone przez filtr",
}
