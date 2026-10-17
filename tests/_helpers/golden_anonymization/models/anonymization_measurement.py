import dataclasses
from collections.abc import Mapping

from tests._helpers.golden_anonymization.models.anonymization_outcome import AnonymizationOutcome
from tests._helpers.golden_anonymization.models.kind_count import KindCount


@dataclasses.dataclass(frozen=True)
class AnonymizationMeasurement:
    """Pomiar anonimizatora na jednym zestawie: ocena każdego przypadku i liczniki na rodzaj."""

    outcomes:  tuple[AnonymizationOutcome, ...]  # w kolejności przypadków zestawu
    leaks:     Mapping[str, KindCount]           # rodzaj danej -> przecieki, np. {"PESEL": …}
    destroyed: Mapping[str, KindCount]           # rodzaj wiedzy -> zniszczone, np. {"NUMER": …}
