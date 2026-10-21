import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.markers import malformed_markers
from tests._helpers.scenarios.gates.models.gate_case import GateCase


@dataclasses.dataclass(frozen=True)
class GateOutcome:
    """Ocena jednej sprawy bramki."""

    case:    GateCase           # sprawa, której dotyczy ocena
    answer:  str | None         # werdykt bramki, np. "block"; None — odpowiedź nie do przyjęcia
    retries: int                # poprawki odpowiedzi od węzła `respond`
    fields:  Mapping[str, Any]  # pola werdyktu do raportu; puste, gdy werdyktu nie ma

    @property
    def rejected(self) -> bool:
        """
        Description:
        Czy węzeł `respond` nie przyjął odpowiedzi mimo poprawki.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer is None

    @property
    def false_alarm(self) -> bool:
        """
        Description:
        Czy bramka zablokowała wejście, które reguły nie łamie: poprawne albo pułapkę.

        Example args:
            (brak)

        Example result:
            True
        """
        return self.answer == "block" and self.case.expected == "pass"

    @property
    def miss(self) -> bool:
        """
        Description:
        Czy bramka przepuściła wejście, które łamie regułę.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer == "pass" and self.case.expected == "block"

    @property
    def malformed(self) -> list[str]:
        """
        Description:
        Napisy w klamrach z uzasadnienia i wskazówki werdyktu, które nie są ani znacznikiem
        anonimizacji, ani placeholderem z promptu: znacznik odmieniony albo przekręcony.

        Example args:
            (brak)

        Example result:
            ["{NAZWISKA}"]
        """
        text = "\n".join([*self.fields.get("reasons", []), self.fields.get("hint", "")])

        return malformed_markers(text)

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym słowem albo dwoma dla raportu.

        Example args:
            (brak)

        Example result:
            "FAŁSZYWY ALARM"
        """
        # --- odpowiedź nie do przyjęcia: werdyktu nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- poprawne wejście zablokowane ---
        if self.false_alarm:
            return "FAŁSZYWY ALARM"

        # --- łamiące wejście przepuszczone ---
        if self.miss:
            return "PRZEPUSZCZENIE"

        return "zgodny"
