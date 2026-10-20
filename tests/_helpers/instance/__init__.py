"""
Description:
Stan instancji w testach: serwis liczący indeksy na atrapach klientów Qdranta i Postgresa
i aplikacja, której trasa `GET /instance` dostaje podany serwis.

Logika leży w `helper.py`, stałe w `constants.py`, próbki w `samples.py`; testy importują logikę
i stałe z pakietu, a próbki z ich modułu.
"""

from tests._helpers.instance.constants import (
    DOCS_COLLECTION,
    QDRANT_URL,
    TICKETS_COLLECTION,
    VECTOR_SIZE,
)
from tests._helpers.instance.helper import (
    app_with_inspector,
    counting_postgres,
    counting_qdrant,
    failing_postgres,
    failing_qdrant,
    inspector_on,
    scripted_inspector,
)

__all__ = [
    "app_with_inspector",
    "counting_postgres",
    "counting_qdrant",
    "DOCS_COLLECTION",
    "failing_postgres",
    "failing_qdrant",
    "inspector_on",
    "QDRANT_URL",
    "scripted_inspector",
    "TICKETS_COLLECTION",
    "VECTOR_SIZE",
]
