import dataclasses


@dataclasses.dataclass(frozen=True)
class TimingSummary:
    """Czas spraw jednego przebiegu w trzech liczbach, w sekundach."""

    median:  float  # np. 3.1
    p90:     float  # np. 5.4 — 90% spraw trwało najwyżej tyle
    maximum: float  # np. 9.8
