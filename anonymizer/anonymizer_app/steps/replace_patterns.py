"""
Description:
Zamiana danych o stałym kształcie na znaczniki: przepuszcza tekst przez wszystkie warianty
wszystkich wzorców, wybiera miejsca, które na siebie nie zachodzą, i zamienia każde na znacznik
jego rodzaju (`{PESEL}`, `{ADRES}`…). Pierwszy krok silnika anonimizacji; osoby wskazuje dopiero
model w kolejnym kroku (p. 19.5).

Przykład:

    przed: „Pani Barbara, PESEL 85030512840, tel. 600 100 200, ul. Lipowa 12/4, 21-100 Lubartów”
    po:    „Pani Barbara, PESEL {PESEL}, tel. {TELEFON}, ul. {ADRES}”

Kroki:

1. Każdy wariant z `VARIANTS` zwraca swoje miejsca.
2. Miejsca układają się od najdłuższego; przy równej długości wygrywa wariant wcześniejszy
   w `PATTERNS`, a potem miejsce wcześniejsze w tekście.
3. Po kolei bierze się każde miejsce, które nie zachodzi na wzięte wcześniej.
4. Wzięte miejsca zamienia się od końca tekstu, żeby zamiana nie przesuwała pozostałych.

O czym pamiętać przy zmianach:

- Najdłuższe wygrywa, bo dłuższe znalezisko niesie krótsze w sobie: adres z kodem pocztowym
  zawiera ulicę z numerem, a e-mail — imię i nazwisko.
- Wzorce z sumą kontrolną stoją w `PATTERNS` przed telefonem: dziewięć cyfr z poprawną sumą
  REGON-u to REGON, choć mają też kształt telefonu.
- Nowy plik wzorca w `patterns/` trzeba dopisać do `PATTERNS`; test zamiany pilnuje, że
  żadnego nie brakuje.
"""

from anonymizer_app.models.found import Found
from anonymizer_app.patterns import (
    address,
    bank_account,
    edor,
    email,
    id_card,
    nip,
    passport,
    pesel,
    phone_number,
    regon,
)

# Wzorce w kolejności, która rozstrzyga remis dwóch miejsc tej samej długości.
PATTERNS = (
    email,
    edor,
    bank_account,
    regon,
    pesel,
    nip,
    id_card,
    passport,
    phone_number,
    address,
)

# Warianty wszystkich wzorców w tej samej kolejności.
VARIANTS = tuple(variant for pattern in PATTERNS for variant in pattern.VARIANTS)


def find_patterns(
    text: str,  # np. "PESEL 85030512840, tel. 600 100 200"
) -> list[Found]:
    """
    Description:
    Miejsca danych o stałym kształcie, które na siebie nie zachodzą, w kolejności tekstu.
    Kolejne kroki opisuje docstring modułu.

    Example args:
        text="PESEL 85030512840, tel. 600 100 200"

    Example result:
        [Found(kind="PESEL", start=6, end=17), Found(kind="TELEFON", start=24, end=35)]
    """
    # --- miejsca ze wszystkich wariantów, z numerem wariantu do rozstrzygania remisów ---
    candidates = [
        (found, order)
        for order, variant in enumerate(VARIANTS)
        for found in variant(text)
    ]

    ranked = sorted(
        candidates,
        key=lambda candidate: (
            candidate[0].start - candidate[0].end,  # najdłuższe pierwsze
            candidate[1],                           # potem wcześniejszy wariant
            candidate[0].start,                     # potem wcześniejsze miejsce
        ),
    )

    # --- miejsca, które nie zachodzą na wzięte wcześniej ---
    chosen: list[Found] = []

    for found, _ in ranked:
        if all(found.end <= taken.start or taken.end <= found.start for taken in chosen):
            chosen.append(found)

    return sorted(chosen, key=lambda found: found.start)


def replace_patterns(
    text: str,  # np. "PESEL 85030512840, tel. 600 100 200"
) -> str:
    """
    Description:
    Zamienia każde miejsce z `find_patterns()` na znacznik jego rodzaju i nie rusza niczego
    więcej.

    Example args:
        text="PESEL 85030512840, tel. 600 100 200"

    Example result:
        "PESEL {PESEL}, tel. {TELEFON}"
    """
    result = text

    # Od końca tekstu, żeby zamiana nie przesuwała miejsc, które czekają na swoją kolej.
    for found in reversed(find_patterns(text)):
        result = f"{result[:found.start]}{{{found.kind}}}{result[found.end:]}"

    return result
