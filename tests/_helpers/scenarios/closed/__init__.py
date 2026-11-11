"""
Description:
Zestaw scenariuszy trasy zamknięcia zgłoszenia (`POST /tickets/closed`), ocena odpowiedzi trasy
i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`,
raport w `report.py`, a przebieg spraw przez trasę na żywym modelu w `measure.py`; testy
importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py` i pakiet ich
nie wystawia.
"""

from tests._helpers.scenarios.closed.constants import (
    CLOSED_FILE,
    EXPECTED_OUTCOMES,
    OUTCOME_LABELS,
)
from tests._helpers.scenarios.closed.helper import closed_cases, judge_closed_case
from tests._helpers.scenarios.closed.measure import measure_closed_cases
from tests._helpers.scenarios.closed.models.closed_case import ClosedCase
from tests._helpers.scenarios.closed.models.closed_outcome import ClosedOutcome
from tests._helpers.scenarios.closed.report import ClosedReport

__all__ = [
    "CLOSED_FILE",
    "ClosedCase",
    "ClosedOutcome",
    "ClosedReport",
    "closed_cases",
    "EXPECTED_OUTCOMES",
    "judge_closed_case",
    "measure_closed_cases",
    "OUTCOME_LABELS",
]
