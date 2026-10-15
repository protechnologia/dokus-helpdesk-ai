"""
Description:
Golden set zgłoszeń w testach ewaluacyjnych: zapytania, dystraktory, korpus odniesienia z etykietami
przeglądu i pomiary wyszukiwania po znaczeniu oraz filtra jakości.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`;
testy importują wszystko z pakietu.
"""

from tests._helpers.golden_tickets.constants import (
    BUILD_HINT,
    CORPUS_DIR,
    DISTRACTORS_FILE,
    GOLDEN_FILE,
    MAX_DISTRACTORS_WITH_HITS,
    MAX_FALSE_POSITIVES,
    MIN_LABELLED_DROPS,
    MIN_TARGET_FIRST,
    MIN_TARGET_RETURNED,
)
from tests._helpers.golden_tickets.helper import (
    corpus,
    distractor_queries,
    golden_queries,
    measure_filter,
    measure_tickets_vector,
    rejected_ids,
)
from tests._helpers.golden_tickets.models.filter_measurement import FilterMeasurement
from tests._helpers.golden_tickets.models.tickets_vector_measurement import (
    TicketsVectorMeasurement,
)

__all__ = [
    "BUILD_HINT",
    "corpus",
    "CORPUS_DIR",
    "DISTRACTORS_FILE",
    "distractor_queries",
    "FilterMeasurement",
    "GOLDEN_FILE",
    "golden_queries",
    "MAX_DISTRACTORS_WITH_HITS",
    "MAX_FALSE_POSITIVES",
    "measure_filter",
    "measure_tickets_vector",
    "MIN_LABELLED_DROPS",
    "MIN_TARGET_FIRST",
    "MIN_TARGET_RETURNED",
    "rejected_ids",
    "TicketsVectorMeasurement",
]
