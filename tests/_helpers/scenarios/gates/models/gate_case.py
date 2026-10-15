import dataclasses

from tests._helpers.scenarios.gates.constants import EXPECTED_VERDICTS, KIND_LABELS


@dataclasses.dataclass(frozen=True)
class GateCase:
    """Jedno wejście bramki z zestawu: reguła, której dotyczy, i rodzaj sprawy."""

    case_id: str  # np. "g01"
    rule:    int  # np. 1 — numer reguły w zestawie domyślnym, od 1
    kind:    str  # np. "breaks"; także "correct" albo "trap"
    text:    str  # wejście bramki, np. "Dzień dobry,\n\nprosimy Państwa o przesłanie…"

    @property
    def expected(self) -> str:
        """
        Description:
        Werdykt, którego wymaga rodzaj sprawy.

        Example args:
            (brak)

        Example result:
            "block"
        """
        return EXPECTED_VERDICTS[self.kind]

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator, reguła i rodzaj.

        Example args:
            (brak)

        Example result:
            "g01 reguła 1, łamie"
        """
        return f"{self.case_id} reguła {self.rule}, {KIND_LABELS[self.kind]}"
