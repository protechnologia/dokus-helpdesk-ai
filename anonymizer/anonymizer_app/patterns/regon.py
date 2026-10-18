"""
Description:
Wzorzec numeru REGON: 9 albo 14 cyfr z poprawną sumą kontrolną. Każdy wariant to osobna
funkcja.

| wariant                       | przykład                     |
|-------------------------------|------------------------------|
| `find_regon_9_by_checksum()`  | „431025874” → „{REGON}”      |
| `find_regon_14_by_checksum()` | „43102587400016” → „{REGON}” |

O czym pamiętać przy zmianach:

- Bez sumy kontrolnej wzorzec wyciąłby każdy identyfikator w tym kształcie („transakcja
  43102587400010” zostaje bez zmian).
- Dziewięć cyfr to też kształt telefonu. Gdy numer ma poprawną sumę REGON-u, zamiana daje mu
  znacznik REGON-u, bo wzorce z sumą stoją w kolejności przed telefonem
  (`steps/replace_patterns.py`).
"""

import re

from anonymizer_app.models.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "REGON"

# Dziewięć i czternaście cyfr, które nie są częścią dłuższego ciągu cyfr.
NINE_DIGITS     = re.compile(r"(?<!\d)\d{9}(?!\d)")
FOURTEEN_DIGITS = re.compile(r"(?<!\d)\d{14}(?!\d)")

# Wagi cyfr w sumie kontrolnej: ośmiu pierwszych przy 9 cyfrach, trzynastu pierwszych przy 14.
WEIGHTS_9  = (8, 9, 2, 3, 4, 5, 6, 7)
WEIGHTS_14 = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def find_regon_9_by_checksum(
    text: str,  # np. "REGON 431025874"
) -> list[Found]:
    """
    Description:
    Miejsca dziewięciu cyfr z poprawną sumą kontrolną REGON-u.

    Example args:
        text="REGON 431025874"

    Example result:
        [Found(kind="REGON", start=6, end=15)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in NINE_DIGITS.finditer(text)
        if _checksum_ok(match.group(), WEIGHTS_9)
    ]

    return found


def find_regon_14_by_checksum(
    text: str,  # np. "dla oddziału REGON 43102587400016"
) -> list[Found]:
    """
    Description:
    Miejsca czternastu cyfr z poprawną sumą kontrolną REGON-u jednostki lokalnej.

    Example args:
        text="dla oddziału REGON 43102587400016"

    Example result:
        [Found(kind="REGON", start=19, end=33)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in FOURTEEN_DIGITS.finditer(text)
        if _checksum_ok(match.group(), WEIGHTS_14)
    ]

    return found


def _checksum_ok(
    digits:  str,              # np. "431025874"
    weights: tuple[int, ...],  # np. WEIGHTS_9
) -> bool:
    """
    Description:
    Mówi, czy ostatnia cyfra zgadza się z sumą kontrolną z pozostałych. Reszta 10 znaczy cyfrę
    kontrolną 0.

    Example args:
        digits="431025874"
        weights=(8, 9, 2, 3, 4, 5, 6, 7)

    Example result:
        True
    """
    total     = sum(int(digit) * weight for digit, weight in zip(digits[:-1], weights, strict=True))
    remainder = total % 11

    return remainder % 10 == int(digits[-1])


# Warianty w kolejności, w jakiej czyta je zamiana (`steps/replace_patterns.py`).
VARIANTS = (
    find_regon_9_by_checksum,
    find_regon_14_by_checksum,
)
