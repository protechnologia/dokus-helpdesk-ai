"""
Description:
Wzorzec numeru dowodu osobistego: 3 wielkie litery i 6 cyfr, z cyfrą kontrolną. Każdy wariant
to osobna funkcja; dowód ma dziś jeden.

| wariant                         | przykład                |
|---------------------------------|-------------------------|
| `find_id_card_by_check_digit()` | „CBF248213” → „{DOWÓD}” |

O czym pamiętać przy zmianach:

- Bez cyfry kontrolnej wzorzec wyciąłby każdy kod produktu czy sprawy w tym kształcie („kod
  ABC123456” zostaje bez zmian).
- Paszport ma ten sam rachunek cyfry kontrolnej, ale inny kształt i osobny plik
  (`passport.py`): rachunek jest tu powielony świadomie, żeby każdy wzorzec dało się
  czytać i zmieniać osobno.
"""

import re

from anonymizer_app.core_model.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "DOWÓD"

# Trzy litery i sześć cyfr, poza dłuższym ciągiem liter i cyfr.
ID_CARD = re.compile(r"(?<!\w)[A-Z]{3}\d{6}(?!\w)")

# Wagi trzech liter i pięciu cyfr po cyfrze kontrolnej, w kolejności zapisu.
WEIGHTS = (7, 3, 1, 7, 3, 1, 7, 3)


def find_id_card_by_check_digit(
    text: str,  # np. "skan dowodu osobistego CBF248213"
) -> list[Found]:
    """
    Description:
    Miejsca numeru dowodu osobistego z poprawną cyfrą kontrolną (czwarty znak).

    Example args:
        text="skan dowodu osobistego CBF248213"

    Example result:
        [Found(kind="DOWÓD", start=23, end=32)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in ID_CARD.finditer(text)
        if _check_digit_ok(match.group())
    ]

    return found


def _check_digit_ok(
    number: str,  # np. "CBF248213"
) -> bool:
    """
    Description:
    Mówi, czy cyfra kontrolna (czwarty znak) zgadza się z sumą ważoną liter i pięciu ostatnich
    cyfr. Litera liczy się jako swoja pozycja w alfabecie plus 9 (A = 10, Z = 35).

    Example args:
        number="CBF248213"

    Example result:
        True
    """
    values = [ord(char) - 55 for char in number[:3]] + [int(digit) for digit in number[4:]]
    total  = sum(value * weight for value, weight in zip(values, WEIGHTS, strict=True))

    return total % 10 == int(number[3])


# Warianty w kolejności, w jakiej czyta je zamiana (`agent_nodes/replace_patterns/node.py`).
VARIANTS = (
    find_id_card_by_check_digit,
)
