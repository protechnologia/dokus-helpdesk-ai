"""
Description:
Znaczniki anonimizacji w odpowiedzi modelu: które przybyły, które zginęły i które są przekręcone.
Ocena scenariuszy na żywym modelu porównuje nimi wejście grafu z jego wynikiem.

| funkcja               | co zwraca                                                          |
|-----------------------|--------------------------------------------------------------------|
| `markers_in()`        | znaczniki anonimizacji w tekście, z liczbą wystąpień               |
| `malformed_markers()` | napisy w klamrach, które nie są ani znacznikiem, ani placeholderem |
| `lost_markers()`      | znaczniki z wejścia, których w wyniku jest mniej niż w wejściu     |

Przykład: wejście „dzwonila p. {IMIĘ} {NAZWISKO}”, wynik „Dzwoniła Pani {IMIENIA}.” —
`malformed_markers()` daje `["{IMIENIA}"]`, a `lost_markers()` daje `["{IMIĘ}", "{NAZWISKO}"]`.
"""

from collections import Counter

from tests._helpers.markers.constants import ANONYMIZATION_KINDS, BRACED, PROMPT_PLACEHOLDERS


def markers_in(
    text: str,  # np. "Pani {IMIĘ} {NAZWISKO}, tel. {TELEFON}"
) -> Counter[str]:
    """
    Description:
    Znaczniki anonimizacji w tekście, każdy z liczbą wystąpień. Placeholderów z promptów
    i napisów przekręconych nie liczy.

    Example args:
        text="Pani {IMIĘ} {NAZWISKO}, tel. {TELEFON}, zgłoszenie {NR_ZGŁOSZENIA}"

    Example result:
        Counter({"{IMIĘ}": 1, "{NAZWISKO}": 1, "{TELEFON}": 1})
    """
    found = Counter(f"{{{kind}}}" for kind in BRACED.findall(text) if kind in ANONYMIZATION_KINDS)

    return found


def malformed_markers(
    text: str,  # np. "Dzwoniła Pani {IMIENIA} {NAZWISKO}."
) -> list[str]:
    """
    Description:
    Napisy w nawiasach klamrowych, które nie są ani znacznikiem anonimizacji, ani placeholderem
    z promptu: znacznik odmieniony, zapisany innymi literami albo wymyślony.

    Example args:
        text="Dzwoniła Pani {IMIENIA} {NAZWISKO}, tel. {Telefon}."

    Example result:
        ["{IMIENIA}", "{Telefon}"]
    """
    known     = ANONYMIZATION_KINDS | PROMPT_PLACEHOLDERS
    malformed = [f"{{{kind}}}" for kind in BRACED.findall(text) if kind not in known]

    return malformed


def lost_markers(
    source: str,  # np. "dzwonila p. {IMIĘ} {NAZWISKO}, tel {TELEFON}"
    result: str,  # np. "Dzwoniła Pani {NAZWISKO}."
) -> list[str]:
    """
    Description:
    Znaczniki z wejścia, których w wyniku jest mniej, niż było w wejściu — każdy brakujący raz,
    w kolejności pierwszego wystąpienia w wejściu.

    Example args:
        source="dzwonila p. {IMIĘ} {NAZWISKO}, tel {TELEFON}"
        result="Dzwoniła Pani {NAZWISKO}."

    Example result:
        ["{IMIĘ}", "{TELEFON}"]
    """
    missing = markers_in(source) - markers_in(result)
    lost    = [marker for marker in missing.elements()]

    return lost
