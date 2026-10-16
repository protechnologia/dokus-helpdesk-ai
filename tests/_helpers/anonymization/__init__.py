"""
Description:
Anonimizacja w testach: zmyślone zgłoszenie z danymi osobowymi i jego postać po anonimizacji,
fragmenty, których nie wolno zobaczyć w logach, klient usługi `anonymizer` na atrapie
transportu oraz sprawdzenie, czy anonimizator przyjmuje wynik atrapy silnika. Używają go testy
usługi `anonymizer`, klienta w `api` i fabryk, które go budują.

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
    accepts_the_fake_engine,
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
    "accepts_the_fake_engine",
    "anonymizer_client_on",
    "service_answer",
]
