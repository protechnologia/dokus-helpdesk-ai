"""
Description:
Zestaw bramki zamknięcia na prawdziwych zamknięciach z `data/unsafe/golden/graph-gate-close.json`
(p. 33.2): wpisy z etykietami na każdą regułę, wejście bramki, czyli wątek z korpusu ucięty na
zamknięciu, ocena werdyktu, raport i przebieg na żywym modelu. Używają go test spójności zestawu
i test bramki na żywym modelu.

Logika leży w `helper.py`, stałe i progi w `constants.py`, modele w `models/`, raport
w `report.py`, a przebieg na żywym modelu w `measure.py`; testy importują je z pakietu. Próbki
do testów samego helpera leżą w `samples.py` i pakiet ich nie wystawia.
"""

from tests._helpers.golden_gate_close.constants import (
    ANONYMIZATION_MAX_SECONDS,
    ANONYMIZATION_MEDIAN_SECONDS,
    ANONYMIZED_DIR,
    BLOCK_GROUPS,
    CONCURRENCY,
    GOLDEN_FILE,
    GROUP_LABELS,
    KINDS,
    MAX_FALSE_ALARMS,
    MAX_MISSES,
    STRATA,
)
from tests._helpers.golden_gate_close.helper import (
    closing_thread,
    golden_gate_close_cases,
    golden_gate_close_rules_version,
    judge_gate_close_case,
    thread_at_close,
    thread_digest,
    timing_summary,
)
from tests._helpers.golden_gate_close.measure import measure_gate_close_cases
from tests._helpers.golden_gate_close.models.gate_close_outcome import GateCloseOutcome
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase
from tests._helpers.golden_gate_close.models.timing_summary import TimingSummary
from tests._helpers.golden_gate_close.report import GateCloseReport

__all__ = [
    "ANONYMIZATION_MAX_SECONDS",
    "ANONYMIZATION_MEDIAN_SECONDS",
    "ANONYMIZED_DIR",
    "BLOCK_GROUPS",
    "closing_thread",
    "CONCURRENCY",
    "GateCloseOutcome",
    "GateCloseReport",
    "golden_gate_close_cases",
    "golden_gate_close_rules_version",
    "GOLDEN_FILE",
    "GoldenGateCloseCase",
    "GROUP_LABELS",
    "judge_gate_close_case",
    "KINDS",
    "MAX_FALSE_ALARMS",
    "MAX_MISSES",
    "measure_gate_close_cases",
    "STRATA",
    "thread_at_close",
    "thread_digest",
    "timing_summary",
    "TimingSummary",
]
