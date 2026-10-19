"""
Description:
Wzorzec numeru paszportu: 2 wielkie litery i 7 cyfr, z cyfrą kontrolną. Każdy wariant to
osobna funkcja; paszport ma dziś jeden.

| wariant                          | przykład                   |
|----------------------------------|----------------------------|
| `find_passport_by_check_digit()` | „EA0417295” → „{PASZPORT}” |

O czym pamiętać przy zmianach:

- Bez cyfry kontrolnej wzorzec wyciąłby każdy kod produktu czy sprawy w tym kształcie („kod
  AB1234567” zostaje bez zmian).
- Dowód osobisty ma ten sam rachunek cyfry kontrolnej, ale inny kształt i osobny plik
  (`id_card.py`): rachunek jest tu powielony świadomie, żeby każdy wzorzec dało się
  czytać i zmieniać osobno.
"""

import re

from anonymizer_app.core_model.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "PASZPORT"

# Dwie litery i siedem cyfr, poza dłuższym ciągiem liter i cyfr.
PASSPORT = re.compile(r"(?<!\w)[A-Z]{2}\d{7}(?!\w)")

# Wagi dwóch liter i sześciu cyfr po cyfrze kontrolnej, w kolejności zapisu.
WEIGHTS = (7, 3, 1, 7, 3, 1, 7, 3)


def find_passport_by_check_digit(
    text: str,  # np. "paszportem nr EA0417295"
) -> list[Found]:
    """
    Description:
    Miejsca numeru paszportu z poprawną cyfrą kontrolną (trzeci znak).

    Example args:
        text="paszportem nr EA0417295"

    Example result:
        [Found(kind="PASZPORT", start=14, end=23)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in PASSPORT.finditer(text)
        if _check_digit_ok(match.group())
    ]

    return found


def _check_digit_ok(
    number: str,  # np. "EA0417295"
) -> bool:
    """
    Description:
    Mówi, czy cyfra kontrolna (trzeci znak) zgadza się z sumą ważoną liter i sześciu ostatnich
    cyfr. Litera liczy się jako swoja pozycja w alfabecie plus 9 (A = 10, Z = 35).

    Example args:
        number="EA0417295"

    Example result:
        True
    """
    values = [ord(char) - 55 for char in number[:2]] + [int(digit) for digit in number[3:]]
    total  = sum(value * weight for value, weight in zip(values, WEIGHTS, strict=True))

    return total % 10 == int(number[2])


# Warianty w kolejności, w jakiej czyta je zamiana (`agent_nodes/replace_patterns/node.py`).
VARIANTS = (
    find_passport_by_check_digit,
)
