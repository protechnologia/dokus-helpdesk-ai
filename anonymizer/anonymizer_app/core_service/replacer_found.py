"""
Description:
Wybór miejsc danych i ich zamiana na znaczniki. Wspólne dla wzorców i dla węzłów z modelem:
każdy węzeł oddaje miejsca (`Found`), a zamieniają je te dwie funkcje. Miejsca, które na siebie
zachodzą, stają się jednym znacznikiem.

Przykład (adres z modelu niesie ulicę nazwaną od osoby, którą węzeł osób wziął za nazwisko):

    miejsca: ADRES „Kościuszki 8/2, Tarnów” (0–22), NAZWISKO „Kościuszki” (0–10)
    po:      „{ADRES}”

Przykład (dwa miejsca się krzyżują: każde wystaje z innej strony):

    tekst:   „Lipowa 12/4, Lubartów”
    miejsca: ADRES „Lipowa 12/4” (0–11), ADRES „12/4, Lubartów” (7–21)
    po:      „{ADRES}”

Kroki:

1. Miejsca układają się w grupy: miejsce, które zaczyna się przed końcem grupy, do niej
   dołącza. Styk (koniec jednego miejsca to początek drugiego) nie jest zachodzeniem.
2. Grupa daje jedno miejsce od początku pierwszego do końca ostatniego, z rodzajem najdłuższego;
   przy równej długości wygrywa mniejszy priorytet, a potem miejsce wcześniejsze w tekście.
3. Miejsca zamienia się od końca tekstu, żeby zamiana nie przesuwała pozostałych.

O czym pamiętać przy zmianach:

- Najdłuższe nadaje rodzaj, bo dłuższe znalezisko zwykle niesie krótsze w sobie: adres z kodem
  pocztowym zawiera ulicę z numerem, a e-mail — imię i nazwisko.
- Zakres to suma, nie najdłuższe miejsce: przy krzyżowaniu odrzucone krótsze zostawiałoby swoją
  wystającą część jawną („Lipowa {ADRES}”). Gdy jedno miejsce zawiera drugie, suma to po prostu
  dłuższe.
"""

from collections.abc import Sequence

from anonymizer_app.core_model.found import Found


def choose_found(
    candidates: Sequence[tuple[Found, int]],  # np. [(Found(kind="ADRES", …), 0), …]
) -> list[Found]:
    """
    Description:
    Miejsca, które na siebie nie zachodzą, w kolejności tekstu: każda grupa miejsc zachodzących
    na siebie daje jedno. Drugi element pary to priorytet przy remisie długości: mniejszy wygrywa.

    Example args:
        candidates=[(Found(kind="ADRES", start=0, end=11), 0),
                    (Found(kind="ADRES", start=7, end=21), 0)]

    Example result:
        [Found(kind="ADRES", start=0, end=21)]
    """
    groups: list[list[tuple[Found, int]]] = []

    for candidate in sorted(candidates, key=lambda candidate: candidate[0].start):
        # Zaczyna się przed końcem grupy, więc na nią zachodzi; styk zostaje osobnym miejscem.
        if groups and candidate[0].start < max(found.end for found, _ in groups[-1]):
            groups[-1].append(candidate)
        else:
            groups.append([candidate])

    return [_merged(group) for group in groups]


def replace_found(
    text:  str,              # np. "Pani Bronisława, tel. 600 100 200"
    found: Sequence[Found],  # miejsca, które na siebie nie zachodzą, np. z choose_found()
) -> str:
    """
    Description:
    Zamienia każde miejsce na znacznik jego rodzaju i nie rusza niczego więcej.

    Example args:
        text="Pani Bronisława, tel. 600 100 200"
        found=[Found(kind="IMIĘ", start=5, end=15), Found(kind="TELEFON", start=22, end=33)]

    Example result:
        "Pani {IMIĘ}, tel. {TELEFON}"
    """
    result = text

    # Od końca tekstu, żeby zamiana nie przesuwała miejsc, które czekają na swoją kolej.
    for place in sorted(found, key=lambda place: place.start, reverse=True):
        result = f"{result[:place.start]}{{{place.kind}}}{result[place.end:]}"

    return result


def _merged(
    group: Sequence[tuple[Found, int]],  # np. [(Found(kind="ADRES", start=0, end=11), 0), …]
) -> Found:
    """
    Description:
    Jedno miejsce z grupy miejsc zachodzących na siebie: od początku pierwszego do końca
    ostatniego, z rodzajem najdłuższego. Przy równej długości wygrywa mniejszy priorytet,
    a potem miejsce wcześniejsze w tekście.

    Example args:
        group=[(Found(kind="NAZWISKO", start=0, end=10), 1),
               (Found(kind="ADRES", start=0, end=22), 0)]

    Example result:
        Found(kind="ADRES", start=0, end=22)
    """
    longest, _ = min(
        group,
        key=lambda candidate: (
            candidate[0].start - candidate[0].end,  # najdłuższe pierwsze
            candidate[1],                           # potem mniejszy priorytet
            candidate[0].start,                     # potem wcześniejsze miejsce
        ),
    )

    merged = Found(
        kind  = longest.kind,
        start = min(found.start for found, _ in group),
        end   = max(found.end for found, _ in group),
    )

    return merged
