"""
Description:
Zestaw scenariuszy bramek, ocena werdyktu i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, raport w `report.py`, a przebieg spraw na żywym modelu w `measure.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py`
i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.gates.constants import (
    EXPECTED_VERDICTS,
    GATES_FILE,
    KIND_LABELS,
    META_KEY,
)
from tests._helpers.scenarios.gates.helper import (
    gate_sections,
    judge_gate_case,
)
from tests._helpers.scenarios.gates.measure import (
    GateOutcomesOf,
    measure_gate_cases,
)
from tests._helpers.scenarios.gates.models.gate_case import GateCase
from tests._helpers.scenarios.gates.models.gate_outcome import GateOutcome
from tests._helpers.scenarios.gates.models.gate_section import GateSection
from tests._helpers.scenarios.gates.report import GateReport

__all__ = [
    "EXPECTED_VERDICTS",
    "gate_sections",
    "GateCase",
    "GateOutcome",
    "GateOutcomesOf",
    "GateReport",
    "GATES_FILE",
    "GateSection",
    "judge_gate_case",
    "KIND_LABELS",
    "measure_gate_cases",
    "META_KEY",
]
