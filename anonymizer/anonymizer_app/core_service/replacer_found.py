"""
Description:
Wybór miejsc danych, które na siebie nie zachodzą, i ich zamiana na znaczniki. Wspólne dla
wzorców i dla węzłów z modelem: każdy węzeł oddaje miejsca (`Found`), a zamieniają je te dwie
funkcje.

Przykład (adres z modelu niesie ulicę nazwaną od osoby, którą węzeł osób wziął za nazwisko):

    miejsca: ADRES „Kościuszki 8/2, Tarnów” (0–22), NAZWISKO „Kościuszki” (0–10)
    po:      „{ADRES}”

Kroki:

1. Miejsca układają się od najdłuższego; przy równej długości wygrywa mniejszy priorytet,
   a potem miejsce wcześniejsze w tekście.
2. Po kolei bierze się każde miejsce, które nie zachodzi na wzięte wcześniej.
3. Wzięte miejsca zamienia się od końca tekstu, żeby zamiana nie przesuwała pozostałych.

O czym pamiętać przy zmianach:

- Najdłuższe wygrywa, bo dłuższe znalezisko niesie krótsze w sobie: adres z kodem pocztowym
  zawiera ulicę z numerem, a e-mail — imię i nazwisko.
"""

from collections.abc import Sequence

from anonymizer_app.core_model.found import Found


def choose_found(
    candidates: Sequence[tuple[Found, int]],  # np. [(Found(kind="ADRES", …), 0), …]
) -> list[Found]:
    """
    Description:
    Miejsca, które na siebie nie zachodzą, w kolejności tekstu. Drugi element pary to priorytet
    przy remisie długości: mniejszy wygrywa.

    Example args:
        candidates=[(Found(kind="NAZWISKO", start=0, end=10), 1),
                    (Found(kind="ADRES", start=0, end=22), 0)]

    Example result:
        [Found(kind="ADRES", start=0, end=22)]
    """
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            candidate[0].start - candidate[0].end,  # najdłuższe pierwsze
            candidate[1],                           # potem mniejszy priorytet
            candidate[0].start,                     # potem wcześniejsze miejsce
        ),
    )

    chosen: list[Found] = []

    for found, _ in ranked:
        if all(found.end <= taken.start or taken.end <= found.start for taken in chosen):
            chosen.append(found)

    return sorted(chosen, key=lambda found: found.start)


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
