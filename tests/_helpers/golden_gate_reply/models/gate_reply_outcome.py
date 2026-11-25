import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.markers import malformed_markers


@dataclasses.dataclass(frozen=True)
class GateReplyOutcome:
    """Ocena jednej wiadomości z zestawu: werdykt bramki wobec etykiet i czas sprawy."""

    case:    GoldenGateReplyCase  # wpis zestawu, którego dotyczy ocena
    answer:  str | None           # werdykt bramki, np. "block"; None — odpowiedź nie do przyjęcia
    retries: int                  # poprawki odpowiedzi od węzła `respond`
    fields:  Mapping[str, Any]    # pola werdyktu do raportu; puste, gdy werdyktu nie ma
    seconds: float                # ile trwała sprawa bramki, bez anonimizacji

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
        Czy bramka zablokowała wiadomość, która według etykiet nie łamie żadnej reguły.

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
        Czy bramka przepuściła wiadomość, która łamie choć jedną regułę.

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
        text = "\n".join([*self.fields.get("reasons", []), self.fields.get("hint") or ""])

        return malformed_markers(text)

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym słowem albo dwoma dla raportu.

        Example args:
            (brak)

        Example result:
            "PRZEPUSZCZENIE"
        """
        # --- odpowiedź nie do przyjęcia: werdyktu nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- wiadomość poprawna zablokowana ---
        if self.false_alarm:
            return "FAŁSZYWY ALARM"

        # --- wiadomość łamiąca regułę przepuszczona ---
        if self.miss:
            return "PRZEPUSZCZENIE"

        return "zgodny"
