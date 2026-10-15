"""
Description:
Dokumentacja syntetyczna w testach ewaluacyjnych: zestaw zapytań, sprawdzenie indeksu
syntetycznego wobec paczki i pomiary obu wyszukiwań w dokumentacji.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe w `constants.py`;
testy importują wszystko z pakietu.
"""

from tests._helpers.synthetic_docs.constants import (
    BUILD_HINT,
    GOLDEN_FILE,
    MAX_UNANSWERED_WITH_HITS,
    MIN_DISTRACTORS_BELOW,
    MIN_EXPECTED_FIRST,
    PACKAGE_DIR,
)
from tests._helpers.synthetic_docs.helper import (
    collection_differences,
    docs_text_entries,
    docs_vector_entries,
    measure_docs_vector,
    require_no_differences,
    search_docs_text,
    section_files,
    table_differences,
)
from tests._helpers.synthetic_docs.models.docs_vector_measurement import DocsVectorMeasurement

__all__ = [
    "BUILD_HINT",
    "collection_differences",
    "docs_text_entries",
    "docs_vector_entries",
    "DocsVectorMeasurement",
    "GOLDEN_FILE",
    "MAX_UNANSWERED_WITH_HITS",
    "measure_docs_vector",
    "MIN_DISTRACTORS_BELOW",
    "MIN_EXPECTED_FIRST",
    "PACKAGE_DIR",
    "require_no_differences",
    "search_docs_text",
    "section_files",
    "table_differences",
]
