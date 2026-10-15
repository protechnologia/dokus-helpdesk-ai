"""
Description:
Zestaw wstrzyknięć, sprawy sekcji, kontrola dotarcia ataku, ocena sprawy i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, a raport w `report.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.scenarios.injections.constants import (
    ATTACK_SEPARATOR,
    DELIVERING_ROLES,
    INJECTIONS_FILE,
    INTO_CARD,
    INTO_INPUT,
    INTO_RULES,
    INTO_THREAD,
    META_KEY,
)
from tests._helpers.scenarios.injections.helper import (
    attacked_cards,
    attacked_input,
    attacked_threads,
    field_lines,
    found_markers,
    injection_cases,
    injection_sections,
    judge_run,
    reached_model,
)
from tests._helpers.scenarios.injections.models.injection_attack import InjectionAttack
from tests._helpers.scenarios.injections.models.injection_case import InjectionCase
from tests._helpers.scenarios.injections.models.injection_outcome import InjectionOutcome
from tests._helpers.scenarios.injections.models.injection_section import InjectionSection
from tests._helpers.scenarios.injections.report import InjectionReport

__all__ = [
    "ATTACK_SEPARATOR",
    "attacked_cards",
    "attacked_input",
    "attacked_threads",
    "DELIVERING_ROLES",
    "field_lines",
    "found_markers",
    "injection_cases",
    "injection_sections",
    "InjectionAttack",
    "InjectionCase",
    "InjectionOutcome",
    "InjectionReport",
    "INJECTIONS_FILE",
    "InjectionSection",
    "INTO_CARD",
    "INTO_INPUT",
    "INTO_RULES",
    "INTO_THREAD",
    "judge_run",
    "META_KEY",
    "reached_model",
]
