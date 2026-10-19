"""
Description:
Wzorzec numeru PESEL: 11 cyfr. Każdy wariant to osobna funkcja.

| wariant                               | przykład                                |
|---------------------------------------|-----------------------------------------|
| `find_pesel_by_checksum()`            | „92112304576” → „{PESEL}”               |
| `find_pesel_with_error_after_label()` | „PESEL 85030512843” → „PESEL {PESEL}”   |
|                                       | „pesel: 85030512843” → „pesel: {PESEL}” |

O czym pamiętać przy zmianach:

- PESEL z błędną sumą po etykiecie to wpisana z pomyłką dana osoby, a jedenaście cyfr bez
  etykiety i z błędną sumą to zwykle identyfikator, który ma zostać („identyfikator
  20260506118” zostaje bez zmian).
- Granicą są cyfry, nie słowa: numer sklejony z literą („nr85030512840”) też jest daną.
"""

import re

from anonymizer_app.core_model.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "PESEL"

# Jedenaście cyfr, które nie są częścią dłuższego ciągu cyfr (numer przesyłki, konto).
ELEVEN_DIGITS = re.compile(r"(?<!\d)\d{11}(?!\d)")

# Jedenaście cyfr zaraz po etykiecie, także z dwukropkiem i w notatce małymi literami.
AFTER_LABEL = re.compile(r"\bPESEL[ \t\xa0]*:?[ \t\xa0]*(?P<value>\d{11})(?!\d)", re.IGNORECASE)

# Wagi cyfr PESEL-u w sumie kontrolnej, od pierwszej do dziesiątej.
WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


def find_pesel_by_checksum(
    text: str,  # np. "Pismo od pana 92112304576 przechodzi."
) -> list[Found]:
    """
    Description:
    Miejsca jedenastu cyfr z poprawną sumą kontrolną PESEL-u, bez względu na to, co stoi obok.

    Example args:
        text="Pismo od pana 92112304576 przechodzi."

    Example result:
        [Found(kind="PESEL", start=14, end=25)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in ELEVEN_DIGITS.finditer(text)
        if _checksum_ok(match.group())
    ]

    return found


def find_pesel_with_error_after_label(
    text: str,  # np. "Numer PESEL 85030512843 jest nieprawidłowy"
) -> list[Found]:
    """
    Description:
    Miejsca jedenastu cyfr z błędną sumą kontrolną zaraz po słowie „PESEL”: PESEL wpisany
    z pomyłką. Numer z poprawną sumą łapie `find_pesel_by_checksum()`. Etykieta nie należy do
    danej.

    Example args:
        text="Numer PESEL 85030512843 jest nieprawidłowy"

    Example result:
        [Found(kind="PESEL", start=12, end=23)]
    """
    found = [
        Found.from_match(KIND, match, "value")
        for match in AFTER_LABEL.finditer(text)
        if not _checksum_ok(match.group("value"))
    ]

    return found


def _checksum_ok(
    digits: str,  # np. "92112304576"
) -> bool:
    """
    Description:
    Mówi, czy ostatnia cyfra zgadza się z sumą kontrolną z dziesięciu pierwszych.

    Example args:
        digits="92112304576"

    Example result:
        True
    """
    total = sum(int(digit) * weight for digit, weight in zip(digits[:10], WEIGHTS, strict=True))

    return (10 - total % 10) % 10 == int(digits[-1])


# Warianty w kolejności, w jakiej czyta je zamiana (`agent_nodes/replace_patterns/node.py`).
VARIANTS = (
    find_pesel_by_checksum,
    find_pesel_with_error_after_label,
)
