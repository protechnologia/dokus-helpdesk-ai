import dataclasses

from tests._helpers.golden_anonymization.models.anonymization_case import AnonymizationCase


@dataclasses.dataclass(frozen=True)
class AnonymizationSet:
    """Jeden plik golden setu anonimizatora: zestaw zmyślony albo próbka korpusu."""

    name:      str                            # z metryczki, np. "anonymization-v1"
    synthetic: bool                           # z metryczki: True — zestaw zmyślony
    cases:     tuple[AnonymizationCase, ...]  # przypadki w kolejności pliku
