"""
Description:
Zestaw scenariuszy „pytań już nie trzeba”, ocena odpowiedzi i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, raport w `report.py`, a przebieg spraw na żywym modelu w `measure.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py`
i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.questions.constants import (
    META_KEY,
    QUESTIONS_FILE,
)
from tests._helpers.scenarios.questions.helper import (
    judge_questions_case,
    questions_sections,
)
from tests._helpers.scenarios.questions.measure import (
    QuestionsOutcomesOf,
    measure_questions_cases,
)
from tests._helpers.scenarios.questions.models.questions_case import QuestionsCase
from tests._helpers.scenarios.questions.models.questions_outcome import QuestionsOutcome
from tests._helpers.scenarios.questions.models.questions_section import QuestionsSection
from tests._helpers.scenarios.questions.report import QuestionsReport

__all__ = [
    "judge_questions_case",
    "measure_questions_cases",
    "META_KEY",
    "QUESTIONS_FILE",
    "questions_sections",
    "QuestionsCase",
    "QuestionsOutcome",
    "QuestionsOutcomesOf",
    "QuestionsReport",
    "QuestionsSection",
]
