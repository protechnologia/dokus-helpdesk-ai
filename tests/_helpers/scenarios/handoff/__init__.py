"""
Description:
Zestaw scenariuszy przekazania sprawy, ocena wiadomości i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`, raport
w `report.py`, a przebieg spraw na żywym modelu w `measure.py`; testy importują wszystko z pakietu.
Próbki do testów samego helpera leżą w `samples.py` i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.handoff.constants import (
    EXAMPLE_PHRASES,
    FAREWELL,
    GREETING,
    HANDOFF_FILE,
    HANDOVER_WORDS,
    META_KEY,
    MIN_PARAGRAPHS,
    PROMISES,
)
from tests._helpers.scenarios.handoff.helper import (
    handoff_sections,
    judge_handoff_case,
    layout_problems,
)
from tests._helpers.scenarios.handoff.measure import (
    HandoffOutcomesOf,
    measure_handoff_cases,
)
from tests._helpers.scenarios.handoff.models.handoff_case import HandoffCase
from tests._helpers.scenarios.handoff.models.handoff_outcome import HandoffOutcome
from tests._helpers.scenarios.handoff.models.handoff_section import HandoffSection
from tests._helpers.scenarios.handoff.report import HandoffReport

__all__ = [
    "EXAMPLE_PHRASES",
    "FAREWELL",
    "GREETING",
    "HANDOFF_FILE",
    "handoff_sections",
    "HandoffCase",
    "HandoffOutcome",
    "HandoffOutcomesOf",
    "HandoffReport",
    "HandoffSection",
    "HANDOVER_WORDS",
    "judge_handoff_case",
    "layout_problems",
    "measure_handoff_cases",
    "META_KEY",
    "MIN_PARAGRAPHS",
    "PROMISES",
]
