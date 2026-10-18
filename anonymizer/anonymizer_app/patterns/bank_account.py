"""
Description:
Wzorzec numeru konta bankowego: 26 cyfr z poprawną sumą IBAN. Każdy wariant to osobna funkcja;
konto ma dziś jeden.

| wariant                      | przykład                                         |
|------------------------------|--------------------------------------------------|
| `find_account_by_checksum()` | „PL30 1160 2202 0000 0003 1245 8701” → „{KONTO}” |
|                              | „PL30116022020000000312458701” → „{KONTO}”       |
|                              | „92 1020 1026 0000 1502 0345 6789” → „{KONTO}”   |
|                              | „92102010260000150203456789” → „{KONTO}”         |

O czym pamiętać przy zmianach:

- „PL” przed numerem należy do danej: „PL30116022020000000312458701” zamienia się w całości.
- Suma IBAN liczy się z kodem kraju, więc numer bez „PL” sprawdza się tak, jakby „PL” stało
  przed nim: polskie konto bez kodu kraju to wciąż polskie konto.
"""

import re

from anonymizer_app.models.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "KONTO"

# Dwie cyfry kontrolne i sześć grup po cztery, ze spacją między grupami albo bez, z „PL” przed
# numerem albo bez; poza dłuższym ciągiem liter i cyfr.
TWENTY_SIX_DIGITS = re.compile(r"(?<!\w)(?:PL[ \t\xa0]?)?\d{2}(?:[ \t\xa0]?\d{4}){6}(?!\d)")

# „PL” zapisane cyframi, tak jak wchodzi do sumy IBAN (P = 25, L = 21).
COUNTRY_CODE = "2521"


def find_account_by_checksum(
    text: str,  # np. "na rachunek 92 1020 1026 0000 1502 0345 6789."
) -> list[Found]:
    """
    Description:
    Miejsca 26 cyfr z poprawną sumą IBAN, w każdym z dopuszczalnych zapisów.

    Example args:
        text="na rachunek 92 1020 1026 0000 1502 0345 6789."

    Example result:
        [Found(kind="KONTO", start=12, end=44)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in TWENTY_SIX_DIGITS.finditer(text)
        if _checksum_ok(re.sub(r"\D", "", match.group()))
    ]

    return found


def _checksum_ok(
    digits: str,  # np. "92102010260000150203456789"
) -> bool:
    """
    Description:
    Mówi, czy numer przechodzi sumę IBAN: cyfry kontrolne i kod kraju przeniesione na koniec dają
    liczbę z resztą 1 z dzielenia przez 97.

    Example args:
        digits="92102010260000150203456789"

    Example result:
        True
    """
    return int(f"{digits[2:]}{COUNTRY_CODE}{digits[:2]}") % 97 == 1


# Warianty w kolejności, w jakiej czyta je zamiana (`steps/replace_patterns.py`).
VARIANTS = (
    find_account_by_checksum,
)
