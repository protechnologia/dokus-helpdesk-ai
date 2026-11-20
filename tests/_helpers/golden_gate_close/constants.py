"""
Description:
Stałe zestawu bramki zamknięcia na prawdziwych zamknięciach (p. 33.2): plik zestawu, wątki po
anonimizacji, z których powstaje wejście bramki, i warstwy doboru.
"""

from pathlib import Path

# Zestaw: zamknięcia z korpusu instancji z etykietami na każdą regułę bramki. Dane klienta, poza
# repo.
GOLDEN_FILE = Path("data/unsafe/golden/gate-close.json")

# Wątki po anonimizacji, z których test składa wejście bramki: ten sam tekst, który poszedł do
# modelu przy masowym imporcie, ucięty na zamknięciu.
ANONYMIZED_DIR = Path("data/unsafe/corpus/anonymized")

# Warstwy doboru w kolejności, w jakiej je losowano: każde zgłoszenie trafia do pierwszej, do
# której pasuje, więc warstwy się nie nakładają.
STRATA = ("longest", "mail", "rejected", "random")

# Rodzaje zgłoszeń: sprawa (problem albo prośba) i powiadomienie, które sprawą nie jest
# (zapowiedź aktualizacji, wykaz zmian); błędy bramki liczy się na sprawach, a powiadomienia
# osobno (decyzja 2026-11-20).
KINDS = ("sprawa", "powiadomienie")
