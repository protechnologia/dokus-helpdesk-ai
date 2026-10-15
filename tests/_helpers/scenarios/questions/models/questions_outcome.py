import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.questions.models.questions_case import QuestionsCase


@dataclasses.dataclass(frozen=True)
class QuestionsOutcome:
    """Ocena jednej sprawy."""

    case:    QuestionsCase      # sprawa, której dotyczy ocena
    asked:   bool | None        # model oddał pytania; None — odpowiedź nie do przyjęcia
    retries: int                # poprawki odpowiedzi od węzła `respond`
    fields:  Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

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
        return self.asked is None

    @property
    def needless(self) -> bool:
        """
        Description:
        Czy model pytał, choć fakty ze zgłoszenia rozstrzygały sprawę.

        Example args:
            (brak)

        Example result:
            True
        """
        return self.asked is True and not self.case.questions

    @property
    def missing(self) -> bool:
        """
        Description:
        Czy model oddał „pytań już nie trzeba”, choć fakty zostawiały konkurujące przyczyny.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.asked is False and self.case.questions

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu.

        Example args:
            (brak)

        Example result:
            "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"
        """
        # --- odpowiedź nie do przyjęcia: wyniku nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- pytania przy sprawie, którą fakty rozstrzygają ---
        if self.needless:
            return "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"

        # --- brak pytań przy sprawie, której fakty nie rozstrzygają ---
        if self.missing:
            return "BEZ PYTAŃ, CHOĆ PRZYCZYNY KONKURUJĄ"

        return "zgodny"
