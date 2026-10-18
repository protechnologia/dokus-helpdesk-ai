"""
Description:
Wzorce usługi `anonymizer` w testach (p. 19.4): tekst po zamianie miejscami z jednego wariantu,
zamiana wszystkimi wzorcami w kształcie funkcji anonimizującej z golden setu, odczyt pomiaru
wzorców, rodzaje danych od wzorców i progi pomiaru na obu zestawach.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.patterns.constants import (
    MAX_LEAKS_SAFE,
    MAX_LEAKS_UNSAFE,
    PATTERN_KINDS,
)
from tests._helpers.patterns.helper import (
    Variant,
    anonymize_with_patterns,
    destroyed_fragments,
    kinds_over_threshold,
    leaked_fragments,
    removed_kinds,
    replaced_by,
)

__all__ = [
    "MAX_LEAKS_SAFE",
    "MAX_LEAKS_UNSAFE",
    "PATTERN_KINDS",
    "Variant",
    "anonymize_with_patterns",
    "destroyed_fragments",
    "kinds_over_threshold",
    "leaked_fragments",
    "removed_kinds",
    "replaced_by",
]
