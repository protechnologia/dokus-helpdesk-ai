"""
Description:
Wzorzec adresu e-mail, sam kształt. Każdy wariant to osobna funkcja.

| wariant                     | przykład                                  |
|-----------------------------|-------------------------------------------|
| `find_email()`              | „<m.kowalczyk@lipno.pl>” → „<{EMAIL}>”    |
|                             | „[mailto:jan@ug.pl]” → „[mailto:{EMAIL}]” |
| `find_email_with_at_word()` | „m.kowalczyk (at) lipno.pl” → „{EMAIL}”   |
|                             | „jan[at]ug.pl” → „{EMAIL}”                |
|                             | „jan.nowak (małpa) gmail.com” → „{EMAIL}” |

Słowo zamiast „@” stoi też w nawiasie klamrowym („{at}”), a spacje wokół nawiasu są dowolne.

O czym pamiętać przy zmianach:

- Samo „at” bez nawiasu („jan at ug.pl”) nie jest wariantem: tak samo wygląda linia śladu
  stosu („Exception at com.foo.Bar”), a jej zamiana zniszczyłaby kod błędu.
- Imię i nazwisko w części przed „@” znikają razem z adresem, więc model wskazujący osoby
  (p. 19.5) już ich tam nie zobaczy.
"""

import re

from anonymizer_app.core_model.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "EMAIL"

# Część przed „@” z literami, cyframi, kropką, plusem i myślnikiem; domena z co najmniej jedną
# kropką. Kropka na końcu zdania nie wchodzi do adresu.
LOCAL  = r"(?<![\w.+-])[\w.+-]+"
DOMAIN = r"[\w-]+(?:\.[\w-]+)+"

ADDRESS = re.compile(rf"{LOCAL}@{DOMAIN}")

# „@” zapisane słowem w nawiasie okrągłym, kwadratowym albo klamrowym.
AT_WORD         = r"[ \t\xa0]*[(\[{][ \t\xa0]*(?:at|małpa)[ \t\xa0]*[)\]}][ \t\xa0]*"
ADDRESS_AT_WORD = re.compile(rf"{LOCAL}{AT_WORD}{DOMAIN}", re.IGNORECASE)


def find_email(
    text: str,  # np. "z [mailto:jan.kowalski@gmina-bory.pl] na kowalski.jan1980@gmail.com"
) -> list[Found]:
    """
    Description:
    Miejsca adresów e-mail zapisanych z „@”.

    Example args:
        text="z [mailto:jan.kowalski@gmina-bory.pl] na kowalski.jan1980@gmail.com"

    Example result:
        [Found(kind="EMAIL", start=10, end=36), Found(kind="EMAIL", start=41, end=67)]
    """
    return [Found.from_match(KIND, match) for match in ADDRESS.finditer(text)]


def find_email_with_at_word(
    text: str,  # np. "pisać na m.kowalczyk (at) lipno.pl"
) -> list[Found]:
    """
    Description:
    Miejsca adresów e-mail, w których zamiast „@” stoi słowo w nawiasie.

    Example args:
        text="pisać na m.kowalczyk (at) lipno.pl"

    Example result:
        [Found(kind="EMAIL", start=9, end=34)]
    """
    return [Found.from_match(KIND, match) for match in ADDRESS_AT_WORD.finditer(text)]


# Warianty w kolejności, w jakiej czyta je zamiana (`agent_nodes/replace_patterns/node.py`).
VARIANTS = (
    find_email,
    find_email_with_at_word,
)
