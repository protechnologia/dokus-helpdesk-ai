"""
Description:
Stałe zestawu bramki zamknięcia na prawdziwych zamknięciach (p. 33.2): plik zestawu, wątki po
anonimizacji, z których powstaje wejście bramki, warstwy doboru, grupy wpisów, ustawienia
pomiaru na żywym modelu i jego progi.
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

# Grupy wpisów w kolejności raportu, z nazwą po polsku. Grupa mówi, jakiego werdyktu wymaga wpis:
# przejść ma tylko sprawa, która spełnia obie reguły, a powiadomienie ma zostać zablokowane
# niezależnie od reguł (GAT-001).
GROUP_LABELS = {
    "pass":   "spełnia obie reguły",
    "rule1":  "łamie regułę 1",
    "rule2":  "łamie regułę 2",
    "both":   "łamie obie reguły",
    "notice": "powiadomienie",
}

# Grupy, w których bramka ma zablokować: przepuszczenia liczy się w każdej osobno, bo reguła 1
# jest złamana tylko w kilku sprawach i zginęłaby w sumie.
BLOCK_GROUPS = ("rule1", "rule2", "both", "notice")

# Ile zamknięć naraz idzie do modelu (decyzja 2026-11-25): przebieg trwa kilka minut, a czas
# sprawy jest bliski czasowi jednego zamknięcia na produkcji i nie trafia na limit dostawcy.
CONCURRENCY = 4

# Czas anonimizacji wątku korpusu na Bieliku z pomiaru z 2026-10-19 (jedno żądanie naraz). Test
# idzie bez poda, więc raport dolicza go do czasu bramki, żeby czas porównać z cierpliwością UI
# helpdesku.
ANONYMIZATION_MEDIAN_SECONDS = 2.0
ANONYMIZATION_MAX_SECONDS    = 6.5

# Progi pomiaru: gorszy wynik z dwóch przebiegów na `gpt-6.1-sol` (2026-11-25, reguły w wersji 1).
# Fałszywe alarmy liczy się wśród 61 spraw, które spełniają obie reguły (było 18 i 19),
# a przepuszczenia osobno w każdej grupie blokad. Progi pilnują, żeby nie było gorzej; to nie
# jest stan docelowy (p. 33.2.3).
MAX_FALSE_ALARMS = 19
MAX_MISSES = {
    "rule1":  1,
    "rule2":  0,
    "both":   0,
    "notice": 1,
}
