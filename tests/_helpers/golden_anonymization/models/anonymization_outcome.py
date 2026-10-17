import dataclasses

from tests._helpers.golden_anonymization.models.anonymization_case import AnonymizationCase
from tests._helpers.golden_anonymization.models.fragment import Fragment


@dataclasses.dataclass(frozen=True)
class AnonymizationOutcome:
    """Ocena tekstu po anonimizacji jednego przypadku."""

    case:      AnonymizationCase     # przypadek, którego dotyczy ocena
    leaked:    tuple[Fragment, ...]  # dane z `remove`, które zostały w wyniku choćby częścią
    destroyed: tuple[Fragment, ...]  # wiedza z `keep`, której w wyniku jest mniej niż w wejściu

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem: „zgodny” albo lista przecieków i zniszczonej wiedzy. Przy próbce
        korpusu bez samych fragmentów, tylko rodzaj z numerem.

        Example args:
            (brak)

        Example result:
            "przecieki: TELEFON „600 123 456”; zniszczone: NUMER „00012345678”"
        """
        problems = [
            f"{name}: {', '.join(fragment.shown(self.case.synthetic) for fragment in found)}"
            for name, found in (
                ("przecieki",  self.leaked),
                ("zniszczone", self.destroyed),
            )
            if found
        ]

        return "; ".join(problems) if problems else "zgodny"
