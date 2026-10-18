"""
Description:
Wzorzec adresu: ulica z numerem, kod pocztowy, miejscowość, sam kształt. Adres nie ma stałej
postaci, więc wzorzec szuka jednej z dwóch kotwic i od niej rozciąga się na resztę adresu. Każda
kotwica to osobna funkcja; wiersze pod funkcją to zapisy, które łapie.

| wariant                           | przykład                                         |
|-----------------------------------|--------------------------------------------------|
| `find_address_at_postal_code()`   | „ul. Lipowa 2, 21-100 Lubin” → „ul. {ADRES}”     |
|                                   | „Polna 20/5, 00-950 Łódź” → „{ADRES}”            |
|                                   | „Polna 20 m. 5, 00-950 Łódź” → „{ADRES}”         |
|                                   | „Polna 20 m 5, 00-950 Łódź” → „{ADRES}”          |
|                                   | „Polna 20 lok. 5 00-950 Łódź” → „{ADRES}”        |
|                                   | „Polna 20 lok 5, 00-950 Łódź” → „{ADRES}”        |
|                                   | „Polna 20 lokal 5, 00-950 Łódź” → „{ADRES}”      |
|                                   | „Polna 20 mieszk. 5, 00-950 Łódź” → „{ADRES}”    |
|                                   | „Polna 20 mieszkanie 5, 00-950 Łódź” → „{ADRES}” |
|                                   | „os. Wiśni 4/7, 31-610 Opole” → „os. {ADRES}”    |
|                                   | „> 26-600 Radom” → „> {ADRES}”                   |
| `find_address_at_street_prefix()` | „ul. Polnej 15, nie” → „ul. {ADRES}, nie”        |
|                                   | „ul Polnej 15” → „ul {ADRES}”                    |
|                                   | „al. Jana Pawła II 5” → „al. {ADRES}”            |
|                                   | „przy ulicy Polnej 15” → „przy ulicy {ADRES}”    |
|                                   | „na placu Wolności 2” → „na placu {ADRES}”       |
|                                   | „rondo Dmowskiego 1” → „rondo {ADRES}”           |
|                                   | „ul. Leśna 9, Toruń” → „ul. {ADRES}”             |
|                                   | „ul. Leśna 9 Toruń” → „ul. {ADRES}”              |
|                                   | „al. Róż 3/5 w Opolu” → „al. {ADRES}”            |

Kotwica i kierunki, w których wzorzec się od niej rozciąga:

| kotwica                      | w lewo                    | w prawo                         |
|------------------------------|---------------------------|---------------------------------|
| kod pocztowy                 | ulica z numerem           | miejscowość                     |
|                              | albo początek linii       |                                 |
| skrót albo słowo przed ulicą | —                         | ulica z numerem, opcjonalnie    |
|                              |                           | miejscowość                     |

Czego wzorzec nie łapie: adresu bez kotwicy („Zielona 4/2, Garwolin”), notatki małymi literami
(„na lipowej 3 w otwocku”) i ulicy, której nazwa zaczyna się od cyfry albo małej litery
(„3 Maja”, „gen. Andersa”).

O czym pamiętać przy zmianach:

- Cały adres stoi w jednej linii: odstępy to spacje, twarde spacje i tabulatory, nigdy znak
  nowej linii. Adres złamany między liniami łapią osobno obie kotwice: ulica po „ul.” w jednej
  linii, kod z miejscowością na początku następnej.
- Kod z miejscowością bez ulicy przed nim łapie się tylko na początku linii: w środku zdania
  („po kodzie 05-400 Daje”) to zwykle nie adres.
- Ulica to od jednego do czterech słów od wielkiej litery („Jana Pawła II”), a miejscowość —
  jedno albo dwa słowa od wielkiej litery, dalej małymi („Zielona Góra”), więc nazwa usługi
  w rodzaju „KSeF” nie dokleja się do miejscowości.
- Wzorzec wytnie też adres urzędu albo firmy: golden set takich adresów nie ocenia.
"""

import re

from anonymizer_app.models.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "ADRES"

# --- słowa ---

# Słowa i skróty przed nazwą ulicy, w zapisach i odmianach, w których przed nią stoją
# („ul. Polna”, „ul Polna”, „przy ulicy Polnej”); wielkość liter nie ma znaczenia. Bez „os” bez
# kropki: „OS Windows 10” wyglądałoby jak osiedle z numerem.
PREFIXES_ULICA    = ("ul.", "ul", "ulica", "ulicy", "ulicę", "ulicą")
PREFIXES_ALEJA    = ("al.", "al", "aleja", "alei", "aleję", "aleją", "aleje", "alejach")
PREFIXES_PLAC     = ("pl.", "pl", "plac", "placu", "placem")
PREFIXES_OSIEDLE  = ("os.", "osiedle", "osiedla", "osiedlu", "osiedlem")
PREFIXES_RONDO    = ("rondo", "ronda", "rondzie")
PREFIXES_SKWER    = ("skwer", "skweru", "skwerze")
PREFIXES_BULWAR   = ("bulwar", "bulwaru", "bulwarze")
PREFIXES_WYBRZEZE = ("wybrzeże", "wybrzeżu")

STREET_PREFIXES = (
    *PREFIXES_ULICA,
    *PREFIXES_ALEJA,
    *PREFIXES_PLAC,
    *PREFIXES_OSIEDLE,
    *PREFIXES_RONDO,
    *PREFIXES_SKWER,
    *PREFIXES_BULWAR,
    *PREFIXES_WYBRZEZE,
)

# Oznaczenia mieszkania przed jego numerem, w każdym zapisie, który wzorzec przyjmuje („12/4”,
# „12 m. 4”, „12 lok 4”).
FLAT_MARKERS = ("/", "m", "m.", "lok", "lok.", "lokal", "mieszk.", "mieszkanie")

# --- kawałki wyrażeń ---

# Wielkie i małe litery, z polskimi.
UPPER = "A-ZĄĆĘŁŃÓŚŹŻ"
LOWER = "a-ząćęłńóśźż"

# Ulica: od jednego do czterech słów od wielkiej litery, także z kropką i łącznikiem w środku
# („Św.”, „Curie-Skłodowskiej”) i liczbą rzymską („II”).
STREET_WORD = rf"[{UPPER}][{UPPER}{LOWER}.\-]*"
STREET      = rf"{STREET_WORD}(?:[ \t\xa0]+{STREET_WORD}){{0,3}}"

# Numer domu z literą i opcjonalnie numer mieszkania po oznaczeniu; za numerem nie stoi już
# litera, cyfra ani „/”. Dłuższe oznaczenia stoją w wyrażeniu pierwsze, żeby „lokal” nie
# dopasowało się jako „lok”.
FLAT   = "|".join(map(re.escape, sorted(FLAT_MARKERS, key=len, reverse=True)))
NUMBER = rf"\d{{1,4}}[a-zA-Z]?(?:[ \t\xa0]*(?:{FLAT})[ \t\xa0]*\d{{1,4}}[a-zA-Z]?)?(?![\w/])"

# Kod pocztowy poza dłuższym ciągiem cyfr i myślników.
POSTAL_CODE = r"(?<![\d-])\d{2}-\d{3}(?![\d-])"

# Miejscowość: jedno albo dwa słowa od wielkiej litery, dalej małymi, także z łącznikiem.
CITY_WORD = rf"[{UPPER}][{LOWER}]+(?:-[{UPPER}][{LOWER}]+)?"
CITY      = rf"{CITY_WORD}(?:[ \t\xa0]+{CITY_WORD})?"

# Słowo albo skrót przed ulicą, poza dłuższym słowem i domeną („ug.pl Polna”). Po kropce odstęp
# jest opcjonalny („ul.Polna”), po słowie bez kropki wymagany. Dłuższe zapisy stoją w wyrażeniu
# pierwsze, żeby „placu” nie dopasowało się jako „pl”.
PREFIXES = "|".join(map(re.escape, sorted(STREET_PREFIXES, key=len, reverse=True)))
PREFIX   = rf"(?<![\w.])(?i:{PREFIXES})(?:(?<=\.)[ \t\xa0]*|[ \t\xa0]+)"

# --- kotwice ---

# Kotwica pierwsza: kod pocztowy z miejscowością, a przed nim ulica z numerem (przecinek przed
# kodem opcjonalny) albo początek linii, także w cytowanym mailu („> ”).
AT_POSTAL_CODE = re.compile(
    rf"(?:^[> \t\xa0]*|(?<![\w-])(?P<street>{STREET}[ \t\xa0]+{NUMBER}[ \t\xa0]*,?[ \t\xa0]*))"
    rf"(?P<code>{POSTAL_CODE}[ \t\xa0]+{CITY})",
    re.MULTILINE,
)

# Kotwica druga: skrót albo słowo przed ulicą, za nim ulica z numerem i opcjonalnie miejscowość
# po przecinku, po samym odstępie albo po „w”; skrót nie należy do danej.
AT_STREET_PREFIX = re.compile(
    rf"{PREFIX}(?P<value>{STREET}[ \t\xa0]+{NUMBER}"
    rf"(?:(?:[ \t\xa0]*,[ \t\xa0]*|[ \t\xa0]+(?:w[ \t\xa0]+)?){CITY})?)"
)

def find_address_at_postal_code(
    text: str,  # np. "zam. ul. Lipowa 12/4, 21-100 Lubartów, system odrzuca"
) -> list[Found]:
    """
    Description:
    Miejsca adresu od kodu pocztowego: miejscowość w prawo, a w lewo ulica z numerem albo
    początek linii, gdy ulica stoi linię wyżej.

    Example args:
        text="zam. ul. Lipowa 12/4, 21-100 Lubartów, system odrzuca"

    Example result:
        [Found(kind="ADRES", start=9, end=37)]
    """
    found = [
        Found(
            kind  = KIND,
            start = match.start("street") if match.group("street") else match.start("code"),
            end   = match.end("code"),
        )
        for match in AT_POSTAL_CODE.finditer(text)
    ]

    return found


def find_address_at_street_prefix(
    text: str,  # np. "z adresu przy al. Wyzwolenia 3/5 w Szczecinie."
) -> list[Found]:
    """
    Description:
    Miejsca adresu od skrótu albo słowa przed ulicą: ulica z numerem w prawo, a za numerem
    miejscowość, jeśli stoi po przecinku, po odstępie albo po „w”.

    Example args:
        text="z adresu przy al. Wyzwolenia 3/5 w Szczecinie."

    Example result:
        [Found(kind="ADRES", start=18, end=45)]
    """
    return [Found.from_match(KIND, match, "value") for match in AT_STREET_PREFIX.finditer(text)]

# Warianty w kolejności, w jakiej czyta je zamiana (`steps/replace_patterns.py`).
VARIANTS = (
    find_address_at_postal_code,
    find_address_at_street_prefix,
)
