"""
Description:
Zestaw scenariuszy rozwiązania, karty i narzędzia sprawy, dopasowanie faktów w treści, licznik
pytań do klienta, ocena sprawy i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, raport w `report.py`, a przebieg spraw na żywym modelu w `measure.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py`
i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.solution.constants import (
    META_KEY,
    NOT_A_QUESTION,
    SOLUTION_FILE,
)
from tests._helpers.scenarios.solution.helper import (
    cards_text,
    case_cards,
    case_tools,
    judge_solution_case,
    mentions,
    mentions_all,
    question_marks,
    solution_sections,
    ticket_subject,
)
from tests._helpers.scenarios.solution.measure import (
    SolutionOutcomesOf,
    measure_solution_cases,
)
from tests._helpers.scenarios.solution.models.solution_case import Fact, SolutionCase
from tests._helpers.scenarios.solution.models.solution_outcome import SolutionOutcome
from tests._helpers.scenarios.solution.models.solution_section import SolutionSection
from tests._helpers.scenarios.solution.report import SolutionReport

__all__ = [
    "case_cards",
    "case_tools",
    "cards_text",
    "Fact",
    "judge_solution_case",
    "measure_solution_cases",
    "mentions",
    "mentions_all",
    "META_KEY",
    "NOT_A_QUESTION",
    "question_marks",
    "solution_sections",
    "SOLUTION_FILE",
    "SolutionCase",
    "SolutionOutcome",
    "SolutionOutcomesOf",
    "SolutionReport",
    "SolutionSection",
    "ticket_subject",
]
