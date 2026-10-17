"""
Description:
Golden set anonimizatora (p. 19.3): zestaw zmyślony i próbka korpusu, ocena tekstu po
anonimizacji (przecieki i zniszczona wiedza), pomiar zestawu z licznikami na rodzaj, sprawdzenie
zaznaczeń i wzorcowa zamiana zaznaczonych danych na znaczniki.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py` i pakiet
ich nie wystawia.
"""

from tests._helpers.golden_anonymization.constants import (
    KEEP_KINDS,
    REMOVE_KINDS,
    SAFE_FILE,
    UNSAFE_FILE,
)
from tests._helpers.golden_anonymization.helper import (
    Anonymize,
    annotation_problems,
    anonymization_set,
    ideal_anonymizer,
    judge_anonymization,
    measure_anonymization,
    replace_marked,
    words,
)
from tests._helpers.golden_anonymization.models.anonymization_case import AnonymizationCase
from tests._helpers.golden_anonymization.models.anonymization_measurement import (
    AnonymizationMeasurement,
)
from tests._helpers.golden_anonymization.models.anonymization_outcome import AnonymizationOutcome
from tests._helpers.golden_anonymization.models.anonymization_set import AnonymizationSet
from tests._helpers.golden_anonymization.models.fragment import Fragment
from tests._helpers.golden_anonymization.models.kind_count import KindCount

__all__ = [
    "annotation_problems",
    "Anonymize",
    "anonymization_set",
    "AnonymizationCase",
    "AnonymizationMeasurement",
    "AnonymizationOutcome",
    "AnonymizationSet",
    "Fragment",
    "ideal_anonymizer",
    "judge_anonymization",
    "KEEP_KINDS",
    "KindCount",
    "measure_anonymization",
    "REMOVE_KINDS",
    "replace_marked",
    "SAFE_FILE",
    "UNSAFE_FILE",
    "words",
]
