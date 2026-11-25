"""
Description:
Zestaw bramki wysyłki na prawdziwych wiadomościach z `data/unsafe/golden/gate-reply.json`
(p. 33.3): wiadomości konsultantów z korpusu z etykietami na każdą regułę wysyłki, wycinanie
wejścia bramki z wątku po anonimizacji, ocena werdyktu, raport i przebieg na żywym modelu.
Używają go test spójności zestawu i test bramki na żywym modelu.

Logika leży w `helper.py`, stałe i progi w `constants.py`, modele w `models/`, raport
w `report.py`, a przebieg na żywym modelu w `measure.py`; testy importują je z pakietu. Próbki
do testów samego helpera leżą w `samples.py` i pakiet ich nie wystawia.
"""

from tests._helpers.golden_gate_reply.constants import (
    ANONYMIZATION_MAX_SECONDS,
    ANONYMIZATION_MEAN_SECONDS,
    ANONYMIZED_DIR,
    CONCURRENCY,
    CONSULTANT_ROLE,
    GOLDEN_FILE,
    MAX_FALSE_ALARMS,
    MAX_MISSES,
    RULES,
    STRATA,
)
from tests._helpers.golden_gate_reply.helper import (
    consultant_message,
    corpus_message,
    golden_gate_reply_cases,
    golden_gate_reply_rules_version,
    judge_gate_reply_case,
    message_digest,
)
from tests._helpers.golden_gate_reply.measure import measure_gate_reply_cases
from tests._helpers.golden_gate_reply.models.gate_reply_outcome import GateReplyOutcome
from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.golden_gate_reply.models.rule_violation import RuleViolation
from tests._helpers.golden_gate_reply.report import GateReplyReport

__all__ = [
    "ANONYMIZATION_MAX_SECONDS",
    "ANONYMIZATION_MEAN_SECONDS",
    "ANONYMIZED_DIR",
    "CONCURRENCY",
    "consultant_message",
    "CONSULTANT_ROLE",
    "corpus_message",
    "GateReplyOutcome",
    "GateReplyReport",
    "GOLDEN_FILE",
    "golden_gate_reply_cases",
    "golden_gate_reply_rules_version",
    "GoldenGateReplyCase",
    "judge_gate_reply_case",
    "MAX_FALSE_ALARMS",
    "MAX_MISSES",
    "measure_gate_reply_cases",
    "message_digest",
    "RuleViolation",
    "RULES",
    "STRATA",
]
