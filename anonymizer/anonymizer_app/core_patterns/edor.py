"""
Description:
Wzorzec adresu do doręczeń elektronicznych (e-Doręczenia): „AE:PL-” i cztery bloki, sam kształt.
Każdy wariant to osobna funkcja; adres ma dziś jeden.

| wariant                     | przykład                                      |
|-----------------------------|-----------------------------------------------|
| `find_e_delivery_address()` | „AE:PL-12345-67890-ABCDE-12” → „{ADRES_EDOR}” |
|                             | „ae:pl-12345-67890-abcde-12” → „{ADRES_EDOR}” |

O czym pamiętać przy zmianach:

- Adres do e-Doręczeń znika zawsze, także adres urzędu, jak e-mail: to adres elektroniczny
  osoby albo podmiotu, a modelowi do odpowiedzi wystarczy, że adres był.
- Ostatnie dwie cyfry to suma kontrolna, ale jej algorytmu nie opublikowano, więc wzorzec
  sprawdza sam kształt; przedrostek „AE:PL-” wystarcza, żeby nie brać za adres niczego innego.
- Nazwa usługi („e-Doręczenia”) zostaje: to wiedza o kanale, nie dana.
"""

import re

from anonymizer_app.core_model.found import Found

# Rodzaj danej i nazwa znacznika w wyniku.
KIND = "ADRES_EDOR"

# „AE:PL-”, dwa bloki po pięć cyfr, blok pięciu liter i dwie cyfry sumy kontrolnej, poza dłuższym
# ciągiem liter i cyfr; wielkość liter bez znaczenia, bo adres bywa przepisywany ręcznie.
ADDRESS = re.compile(r"(?<!\w)AE:PL-\d{5}-\d{5}-[A-Z]{5}-\d{2}(?!\w)", re.IGNORECASE)


def find_e_delivery_address(
    text: str,  # np. "adres do doręczeń AE:PL-12345-67890-ABCDE-12, a"
) -> list[Found]:
    """
    Description:
    Miejsca adresów do doręczeń elektronicznych w kształcie „AE:PL-00000-00000-AAAAA-00”.

    Example args:
        text="adres do doręczeń AE:PL-12345-67890-ABCDE-12, a"

    Example result:
        [Found(kind="ADRES_EDOR", start=18, end=44)]
    """
    return [Found.from_match(KIND, match) for match in ADDRESS.finditer(text)]


# Warianty w kolejności, w jakiej czyta je zamiana (`agent_nodes/replace_patterns/node.py`).
VARIANTS = (
    find_e_delivery_address,
)
