"""
Description:
Golden set zgłoszeń w testach ewaluacyjnych i w teście jego spójności: wpisy z etykietami
przeglądu i zapytaniami, dystraktory, korpus odniesienia i pomiary wyszukiwania po znaczeniu oraz
filtra jakości.

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
    QUERY_DIFFICULTIES,
    QUERY_KINDS,
)
from tests._helpers.golden_tickets.helper import (
    corpus,
    distractor_queries,
    golden_queries,
    golden_set,
    measure_filter,
    measure_tickets_vector,
    not_useful_ids,
)
from tests._helpers.golden_tickets.models.filter_measurement import FilterMeasurement
from tests._helpers.golden_tickets.models.golden_query import GoldenQuery
from tests._helpers.golden_tickets.models.golden_set import GoldenSet
from tests._helpers.golden_tickets.models.golden_ticket import GoldenTicket
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
    "golden_set",
    "GoldenQuery",
    "GoldenSet",
    "GoldenTicket",
    "MAX_DISTRACTORS_WITH_HITS",
    "MAX_FALSE_POSITIVES",
    "measure_filter",
    "measure_tickets_vector",
    "MIN_LABELLED_DROPS",
    "MIN_TARGET_FIRST",
    "MIN_TARGET_RETURNED",
    "not_useful_ids",
    "QUERY_DIFFICULTIES",
    "QUERY_KINDS",
    "TicketsVectorMeasurement",
]
