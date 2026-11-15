"""
Description:
Golden set zgłoszeń w testach ewaluacyjnych i w testach jego spójności: wpisy z etykietami
przeglądu i zapytaniami, dystraktory, zestaw zapytań tekstowych, korpus odniesienia z wątkami
po anonimizacji i pomiary wyszukiwania po znaczeniu, wyszukiwania tekstowego oraz filtra jakości.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`;
testy importują wszystko z pakietu.
"""

from tests._helpers.golden_tickets.constants import (
    BUILD_HINT,
    CORPUS_DIR,
    DISTRACTORS_FILE,
    GOLDEN_COLLECTION,
    GOLDEN_FILE,
    GOLDEN_TABLE,
    MAX_DISTRACTORS_WITH_HITS,
    MAX_FALSE_POSITIVES,
    MIN_LABELLED_DROPS,
    MIN_TARGET_FIRST,
    MIN_TARGET_RETURNED,
    QUERY_DIFFICULTIES,
    QUERY_KINDS,
    TEXT_DISTRACTORS_WITH_HITS,
    TEXT_FILE,
    TEXT_QUERY_KINDS,
    TEXT_TARGET_FIRST,
    TEXT_TARGET_RETURNED,
    THREADS_DIR,
)
from tests._helpers.golden_tickets.helper import (
    contains_phrase,
    corpus,
    distractor_queries,
    golden_queries,
    golden_set,
    golden_text_set,
    golden_thread,
    measure_filter,
    measure_tickets_text,
    measure_tickets_vector,
    not_useful_ids,
)
from tests._helpers.golden_tickets.models.filter_measurement import FilterMeasurement
from tests._helpers.golden_tickets.models.golden_query import GoldenQuery
from tests._helpers.golden_tickets.models.golden_set import GoldenSet
from tests._helpers.golden_tickets.models.golden_text_query import GoldenTextQuery
from tests._helpers.golden_tickets.models.golden_text_set import GoldenTextSet
from tests._helpers.golden_tickets.models.golden_ticket import GoldenTicket
from tests._helpers.golden_tickets.models.tickets_text_measurement import (
    TicketsTextMeasurement,
)
from tests._helpers.golden_tickets.models.tickets_vector_measurement import (
    TicketsVectorMeasurement,
)

__all__ = [
    "BUILD_HINT",
    "contains_phrase",
    "corpus",
    "CORPUS_DIR",
    "DISTRACTORS_FILE",
    "distractor_queries",
    "FilterMeasurement",
    "GOLDEN_COLLECTION",
    "GOLDEN_FILE",
    "GOLDEN_TABLE",
    "golden_queries",
    "golden_set",
    "golden_text_set",
    "golden_thread",
    "GoldenQuery",
    "GoldenSet",
    "GoldenTextQuery",
    "GoldenTextSet",
    "GoldenTicket",
    "MAX_DISTRACTORS_WITH_HITS",
    "MAX_FALSE_POSITIVES",
    "measure_filter",
    "measure_tickets_text",
    "measure_tickets_vector",
    "MIN_LABELLED_DROPS",
    "MIN_TARGET_FIRST",
    "MIN_TARGET_RETURNED",
    "not_useful_ids",
    "QUERY_DIFFICULTIES",
    "QUERY_KINDS",
    "TEXT_DISTRACTORS_WITH_HITS",
    "TEXT_FILE",
    "TEXT_QUERY_KINDS",
    "TEXT_TARGET_FIRST",
    "TEXT_TARGET_RETURNED",
    "THREADS_DIR",
    "TicketsTextMeasurement",
    "TicketsVectorMeasurement",
]
