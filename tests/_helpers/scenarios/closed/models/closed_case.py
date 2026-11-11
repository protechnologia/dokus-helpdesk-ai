import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.closed.constants import OUTCOME_LABELS


@dataclasses.dataclass(frozen=True)
class ClosedCase:
    """Jedno zamknięcie z zestawu: treść żądania do trasy i wynik, którego wymaga."""

    case_id:  str                # np. "c01"
    expected: str                # np. "indexed"; także "blocked" albo "dropped"
    request:  Mapping[str, Any]  # treść żądania, np. {"ticket_id": "90601", "body": "…", …}

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i wynik, którego sprawa wymaga.

        Example args:
            (brak)

        Example result:
            "c01 do indeksów"
        """
        return f"{self.case_id} {OUTCOME_LABELS[self.expected]}"
