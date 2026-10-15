import dataclasses


@dataclasses.dataclass(frozen=True)
class FilterMeasurement:
    """Odrzucenia filtra jakości na korpusie odniesienia, porównane z etykietami przeglądu."""

    labelled_drops:  int  # odrzucone spośród oznaczonych w przeglądzie jako bez wiedzy
    false_positives: int  # odrzucone spośród uznanych w przeglądzie za dobre
