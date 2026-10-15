import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.solution.models.solution_case import SolutionCase


@dataclasses.dataclass(frozen=True)
class SolutionOutcome:
    """Ocena jednej sprawy."""

    case:              SolutionCase       # sprawa, której dotyczy ocena
    rejected:          bool               # węzeł `respond` nie przyjął odpowiedzi mimo poprawki
    text_given:        bool               # wynik ma treść dla klienta, a nie same uwagi
    missing:           tuple[str, ...]    # fakty z `must_mention` spoza treści (pierwszy wariant)
    expected_mention:  bool | None        # wzmianka z `should_mention` w treści; None — nie liczona
    forbidden_mention: bool | None        # wzmianka z `should_not_mention`; None — nie liczona
    sources:           tuple[str, ...]    # klucze źródeł, np. ("tickets:90002",)
    retries:           int                # poprawki odpowiedzi od węzła `respond`
    fields:            Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu.

        Example args:
            (brak)

        Example result:
            "BRAK W TREŚCI: nieodwracaln"
        """
        # --- odpowiedź nie do przyjęcia: wyniku nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- fakty wymagane, a wynik bez treści dla klienta ---
        if self.missing and not self.text_given:
            return "BEZ TREŚCI DLA KLIENTA"

        # --- treść jest, ale bez części wymaganych faktów ---
        if self.missing:
            return f"BRAK W TREŚCI: {', '.join(self.missing)}"

        return "zgodny"
