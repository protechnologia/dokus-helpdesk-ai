"""
Description:
Wzorzec numeru NIP: 10 cyfr z poprawną sumą kontrolną. Każdy wariant to osobna funkcja; NIP ma
dziś jeden.

| wariant                  | przykład                  |
|--------------------------|---------------------------|
| `find_nip_by_checksum()` | „7421365180” → „{NIP}”    |
|                          | „742-136-51-80” → „{NIP}” |
|                          | „742 136 51 80” → „{NIP}” |
|                          | „742 136-51 80” → „{NIP}” |
|                          | „742-136-5180” → „{NIP}”  |
|                          | „742-13-65-180” → „{NIP}” |

O czym pamiętać przy zmianach:

- Bez sumy kontrolnej wzorzec wyciąłby każdy numer zamówienia czy faktury w tym kształcie
  („zamówienie nr 123-456-78-90” zostaje bez zmian).
"""

import re

from anonymizer_app.models.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "NIP"

# Odstęp między grupami cyfr, opcjonalny w każdym miejscu: myślnik, spacja albo twarda spacja.
GAP = r"[ \t\xa0-]?"

# Dziesięć cyfr w układzie 3-3-2-2 albo 3-2-2-3, poza dłuższym ciągiem cyfr i myślników; bez
# odstępów oba układy dają ten sam ciąg dziesięciu cyfr.
LAYOUT_3322 = rf"\d{{3}}{GAP}\d{{3}}{GAP}\d{{2}}{GAP}\d{{2}}"
LAYOUT_3223 = rf"\d{{3}}{GAP}\d{{2}}{GAP}\d{{2}}{GAP}\d{{3}}"
TEN_DIGITS  = re.compile(rf"(?<![\d-])(?:{LAYOUT_3322}|{LAYOUT_3223})(?![\d-])")

# Wagi dziewięciu pierwszych cyfr NIP-u w sumie kontrolnej.
WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def find_nip_by_checksum(
    text: str,  # np. "NIP 742-136-51-80, REGON 431025874"
) -> list[Found]:
    """
    Description:
    Miejsca dziesięciu cyfr z poprawną sumą kontrolną NIP-u, z odstępami między grupami albo bez.

    Example args:
        text="NIP 742-136-51-80, REGON 431025874"

    Example result:
        [Found(kind="NIP", start=4, end=17)]
    """
    found = [
        Found.from_match(KIND, match)
        for match in TEN_DIGITS.finditer(text)
        if _checksum_ok(re.sub(r"\D", "", match.group()))
    ]

    return found


def _checksum_ok(
    digits: str,  # np. "7421365180"
) -> bool:
    """
    Description:
    Mówi, czy ostatnia cyfra zgadza się z sumą kontrolną z dziewięciu pierwszych. Reszta 10 nie
    daje poprawnego NIP-u.

    Example args:
        digits="7421365180"

    Example result:
        True
    """
    total     = sum(int(digit) * weight for digit, weight in zip(digits[:9], WEIGHTS, strict=True))
    remainder = total % 11

    return remainder != 10 and remainder == int(digits[-1])


# Warianty w kolejności, w jakiej czyta je zamiana (`steps/replace_patterns.py`).
VARIANTS = (
    find_nip_by_checksum,
)
