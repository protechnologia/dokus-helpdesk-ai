"""
Description:
Zestaw bramki wysyłki na prawdziwych wiadomościach z `data/unsafe/golden/gate-reply.json`
(p. 33.3): wiadomości konsultantów z korpusu z etykietami na każdą regułę wysyłki i wycinanie
wejścia bramki z wątku po anonimizacji. Używają go test spójności zestawu i test bramki na żywym
modelu.

Logika leży w `helper.py`, stałe w `constants.py`, a modele w `models/`; testy importują je
z pakietu.
"""

from tests._helpers.golden_gate_reply.constants import (
    ANONYMIZED_DIR,
    CONSULTANT_ROLE,
    GOLDEN_FILE,
    STRATA,
)
from tests._helpers.golden_gate_reply.helper import (
    consultant_message,
    corpus_message,
    golden_gate_reply_cases,
    golden_gate_reply_rules_version,
    message_digest,
)
from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.golden_gate_reply.models.rule_violation import RuleViolation

__all__ = [
    "ANONYMIZED_DIR",
    "consultant_message",
    "CONSULTANT_ROLE",
    "corpus_message",
    "GOLDEN_FILE",
    "golden_gate_reply_cases",
    "golden_gate_reply_rules_version",
    "GoldenGateReplyCase",
    "message_digest",
    "RuleViolation",
    "STRATA",
]
