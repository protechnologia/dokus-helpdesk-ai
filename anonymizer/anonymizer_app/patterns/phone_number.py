"""
Description:
Wzorzec numeru telefonu: sam kształt, bez sumy kontrolnej. Każdy wariant to osobna funkcja.

| wariant                        | przykład                              |
|--------------------------------|---------------------------------------|
| `find_mobile()`                | „600 100 200” → „{TELEFON}”           |
|                                | „512-345-678” → „{TELEFON}”           |
|                                | „600 100-200” → „{TELEFON}”           |
|                                | „501234567” → „{TELEFON}”             |
|                                | „+48 512 345 678” → „{TELEFON}”       |
|                                | „(+48) 600 100 200” → „{TELEFON}”     |
|                                | „kom.694111222” → „kom.{TELEFON}”     |
| `find_landline()`              | „81 532 10 15” → „{TELEFON}”          |
|                                | „81 532-10 15” → „{TELEFON}”          |
|                                | „(22) 456 78 90” → „{TELEFON}”        |
|                                | „(081) 532 10 15” → „{TELEFON}”       |
|                                | „+48 22 456-78-90” → „{TELEFON}”      |
|                                | „81 532 10 15 wew. 115” → „{TELEFON}” |
|                                | „81 5321015” → „{TELEFON}”            |
|                                | „81 5321015w.12” → „{TELEFON}”        |
| `find_extension_after_label()` | „tel. 6013” → „tel. {TELEFON}”        |
|                                | „wew. 115” → „wew. {TELEFON}”         |

Między grupami cyfr może stać też twarda spacja i tabulator, a „0048” działa jak „+48”. Numer
wewnętrzny to 3–5 cyfr zaraz po „tel.”, „tel:”, „telefon” albo „wew.”.

O czym pamiętać przy zmianach:

- Telefon nie ma sumy kontrolnej, więc przed numerem nie może stać litera ani cyfra:
  „ZS600100200” to kod, nie telefon. Etykieta sklejona kropką („kom.694111222”) granicy nie
  łamie, a za numerem litera może stać („81 5321015w.12”).
- Twarda spacja między grupami stoi w co czternastym zgłoszeniu korpusu; bez niej w odstępach
  numer z niej przepadałby w całości.
- Numer wewnętrzny po etykiecie łapie tylko wtedy, gdy etykieta stoi tuż przed cyframi:
  „tel. 600 100 200” daje dłuższe miejsce numeru komórkowego, które wygrywa w zamianie.
- Dziewięć cyfr z poprawną sumą REGON-u dostaje znacznik REGON-u: wzorce z sumą stoją
  w kolejności przed telefonem (`steps/replace_patterns.py`).
"""

import re

from anonymizer_app.models.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "TELEFON"

# Odstęp między grupami cyfr: spacja, twarda spacja, tabulator albo myślnik.
GAP = r"[ \t\xa0-]"

# Numer kierunkowy kraju, opcjonalny, także w nawiasie.
COUNTRY = rf"(?:(?:\+|00)48{GAP}?|\(\+48\)[ \t\xa0]?)?"

# Kierunkowy stacjonarny: dwie cyfry, także z zerem przed nimi i w nawiasie.
AREA = r"(?:\(0?\d{2}\)|0?\d{2})"

# Numer wewnętrzny dopisany za stacjonarnym po „w.” albo „wew.”, opcjonalny.
EXTENSION = r"(?:[ \t\xa0]*w(?:ew)?\.[ \t\xa0]*\d{1,5})?"

# Przed numerem nie stoi litera, cyfra ani „+”; za nim nie stoi cyfra.
START = r"(?<![\w+])"
END   = r"(?!\d)"

# Komórkowy: trzy grupy po trzy cyfry, z odstępem między grupami albo bez, także mieszanym.
MOBILE = re.compile(rf"{START}{COUNTRY}\d{{3}}{GAP}?\d{{3}}{GAP}?\d{{3}}{END}")

# Stacjonarny: kierunkowy, odstęp i siedem cyfr w grupach 3-2-2, z odstępem między grupami albo bez,
# z numerem wewnętrznym albo bez. Odstęp po kierunkowym jest wymagany: bez niego dziesięć cyfr
# z zerem na początku brałoby się za telefon.
LANDLINE = re.compile(
    rf"{START}{COUNTRY}{AREA}{GAP}\d{{3}}{GAP}?\d{{2}}{GAP}?\d{{2}}{EXTENSION}{END}"
)

# Numer wewnętrzny: od trzech do pięciu cyfr zaraz po „tel.”, „tel:”, „telefon” albo „wew.”.
EXTENSION_AFTER_LABEL = re.compile(
    r"\b(?:tel(?:efon)?|wew)\.?:?[ \t\xa0]*(?P<value>\d{3,5})(?!\d)",
    re.IGNORECASE,
)


def find_mobile(
    text: str,  # np. "kontakt pod nr 600 100 200 lub +48 512-345-678"
) -> list[Found]:
    """
    Description:
    Miejsca numeru komórkowego w zapisie 3-3-3 albo bez odstępów, z kierunkowym kraju albo bez.

    Example args:
        text="kontakt pod nr 600 100 200 lub +48 512-345-678"

    Example result:
        [Found(kind="TELEFON", start=15, end=26), Found(kind="TELEFON", start=31, end=46)]
    """
    return [Found.from_match(KIND, match) for match in MOBILE.finditer(text)]


def find_landline(
    text: str,  # np. "stacjonarnie (22) 456 78 90 wew. 115"
) -> list[Found]:
    """
    Description:
    Miejsca numeru stacjonarnego: kierunkowy, także w nawiasie, i siedem cyfr w grupach 3-2-2
    albo ciągiem, razem z numerem wewnętrznym dopisanym po „wew.” albo „w.”.

    Example args:
        text="stacjonarnie (22) 456 78 90 wew. 115"

    Example result:
        [Found(kind="TELEFON", start=13, end=36)]
    """
    return [Found.from_match(KIND, match) for match in LANDLINE.finditer(text)]



def find_extension_after_label(
    text: str,  # np. "Tel. 6013"
) -> list[Found]:
    """
    Description:
    Miejsca numeru wewnętrznego: od trzech do pięciu cyfr zaraz po etykiecie telefonu. Etykieta
    nie należy do danej.

    Example args:
        text="Tel. 6013"

    Example result:
        [Found(kind="TELEFON", start=5, end=9)]
    """
    found = [
        Found.from_match(KIND, match, "value")
        for match in EXTENSION_AFTER_LABEL.finditer(text)
    ]

    return found


# Warianty w kolejności, w jakiej czyta je zamiana (`steps/replace_patterns.py`).
VARIANTS = (
    find_mobile,
    find_landline,
    find_extension_after_label,
)
