"""
Description:
Stałe zestawu bramki zamknięcia na prawdziwych zamknięciach (p. 33.2): plik zestawu, wątki po
anonimizacji, z których powstaje wejście bramki, warstwy doboru, grupy wpisów, ustawienia
pomiaru na żywym modelu i jego progi.
"""

from pathlib import Path

# Zestaw: zamknięcia z korpusu instancji z etykietami na każdą regułę bramki. Dane klienta, poza
# repo.
GOLDEN_FILE = Path("data/unsafe/golden/graph-gate-close.json")

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
# przejść ma tylko sprawa, z której widać problem i rozwiązanie, a powiadomienie ma zostać
# zablokowane niezależnie od reguł (ADR-005). Nazwy mówią o etykietach, a nie o numerach reguł, bo
# reguł jest więcej niż etykiet: problem to reguły 1 i 2, rozwiązanie reguły 1 i 3–6.
GROUP_LABELS = {
    "pass":        "widać problem i rozwiązanie",
    "no_problem":  "nie widać problemu",
    "no_solution": "nie widać rozwiązania",
    "neither":     "nie widać problemu ani rozwiązania",
    "notice":      "powiadomienie",
}

# Grupy, w których bramka ma zablokować: przepuszczenia liczy się w każdej osobno, bo spraw bez
# widocznego problemu jest tylko kilka i zginęłyby w sumie.
BLOCK_GROUPS = ("no_problem", "no_solution", "neither", "notice")

# Ile zamknięć naraz idzie do modelu (decyzja 2026-11-25): przebieg trwa kilka minut, a czas
# sprawy jest bliski czasowi jednego zamknięcia na produkcji i nie trafia na limit dostawcy.
CONCURRENCY = 4

# Czas anonimizacji wątku korpusu na Bieliku z pomiaru z 2026-10-19 (jedno żądanie naraz). Test
# idzie bez poda, więc raport dolicza go do czasu bramki, żeby czas porównać z cierpliwością UI
# helpdesku.
ANONYMIZATION_MEDIAN_SECONDS = 2.0
ANONYMIZATION_MAX_SECONDS    = 6.5

# Progi pomiaru: gorszy wynik z dwóch przebiegów na `gpt-6.1-sol`, zmierzony 2026-11-25 na regułach
# i etykietach w wersji 2 (fałszywych alarmów 13 i 14 z 59). Fałszywe alarmy liczy się wśród spraw,
# z których widać problem i rozwiązanie, a przepuszczenia osobno w każdej grupie blokad. Pilnują,
# żeby nie było gorzej; grupa „nie widać problemu” jest na tych etykietach pusta.
MAX_FALSE_ALARMS = 14
MAX_MISSES = {
    "no_problem":  0,
    "no_solution": 2,
    "neither":     0,
    "notice":      1,
}
