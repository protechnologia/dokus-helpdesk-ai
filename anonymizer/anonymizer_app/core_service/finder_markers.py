"""
Description:
Znaczniki, które wstawiła anonimizacja (`{IMIĘ}`, `{TELEFON}`…), i ich zakresy w tekście. Węzły
z modelem pomijają słowa w znacznikach: znacznik to dana już zamieniona, a fragment z nim nie jest
daną z tekstu.
"""

import re

# Znacznik, który wstawiła anonimizacja: nazwa rodzaju w nawiasach klamrowych, bez odstępów.
# Wskazany przez model fragment, który leży w znaczniku albo go niesie, nie jest daną z tekstu.
MARKER = re.compile(r"\{[^{}\s]{1,20}\}")


def marker_spans(
    text: str,  # np. "Pani {IMIĘ}, tel. {TELEFON}"
) -> list[tuple[int, int]]:
    """
    Description:
    Zakresy znaczników w tekście, w kolejności tekstu.

    Example args:
        text="Pani {IMIĘ}, tel. {TELEFON}"

    Example result:
        [(5, 11), (18, 27)]
    """
    return [match.span() for match in MARKER.finditer(text)]
