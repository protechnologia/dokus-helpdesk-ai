"""
Description:
Anonimizacja w testach: zmyślone zgłoszenie z danymi osobowymi i jego postać po anonimizacji,
fragmenty, których nie wolno zobaczyć w logach, oraz klient usługi `anonymizer` na atrapie
transportu. Używają go testy usługi `anonymizer` i klienta w `api`.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.anonymization.constants import (
    ANONYMIZED_TEXT,
    BASE_URL,
    FAKE_ENGINE,
    RAW_TEXT,
    REAL_ENGINE,
    SENSITIVE,
)
from tests._helpers.anonymization.helper import (
    anonymizer_client_on,
    service_answer,
)

__all__ = [
    "ANONYMIZED_TEXT",
    "BASE_URL",
    "FAKE_ENGINE",
    "RAW_TEXT",
    "REAL_ENGINE",
    "SENSITIVE",
    "anonymizer_client_on",
    "service_answer",
]
