"""
Description:
Zestaw bramki zamknięcia na prawdziwych zamknięciach z `data/unsafe/golden/gate-close.json`
(p. 33.2): wpisy z etykietami na każdą regułę i wejście bramki, czyli wątek z korpusu ucięty na
zamknięciu. Używają go test spójności zestawu i test bramki na żywym modelu.

Logika leży w `helper.py`, stałe w `constants.py`, modele w `models/`; testy importują je
z pakietu.
"""

from tests._helpers.golden_gate_close.constants import ANONYMIZED_DIR, GOLDEN_FILE, KINDS, STRATA
from tests._helpers.golden_gate_close.helper import (
    closing_thread,
    golden_gate_close_cases,
    thread_at_close,
    thread_digest,
)
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase

__all__ = [
    "ANONYMIZED_DIR",
    "GOLDEN_FILE",
    "KINDS",
    "STRATA",
    "GoldenGateCloseCase",
    "closing_thread",
    "golden_gate_close_cases",
    "thread_at_close",
    "thread_digest",
]
