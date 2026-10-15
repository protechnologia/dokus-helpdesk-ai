"""
Description:
Zestaw scenariuszy „Popraw”, ocena poprawionego tekstu i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, a raport w `report.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.scenarios.polish.constants import (
    EXTRA_LETTERS,
    LIST_NUMBER,
    META_KEY,
    POLISH_FILE,
)
from tests._helpers.scenarios.polish.helper import (
    judge_polish_case,
    numbers,
    plain,
    polish_sections,
)
from tests._helpers.scenarios.polish.models.polish_case import PolishCase
from tests._helpers.scenarios.polish.models.polish_outcome import PolishOutcome
from tests._helpers.scenarios.polish.models.polish_section import PolishSection
from tests._helpers.scenarios.polish.report import PolishReport

__all__ = [
    "EXTRA_LETTERS",
    "judge_polish_case",
    "LIST_NUMBER",
    "META_KEY",
    "numbers",
    "plain",
    "POLISH_FILE",
    "polish_sections",
    "PolishCase",
    "PolishOutcome",
    "PolishReport",
    "PolishSection",
]
