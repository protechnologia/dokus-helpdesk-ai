import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.reading.models.reading_case import ReadingCase


@dataclasses.dataclass(frozen=True)
class ReadingOutcome:
    """Ocena jednej sprawy."""

    case:          ReadingCase        # sprawa, której dotyczy ocena
    rejected:      bool               # węzeł `respond` nie przyjął odpowiedzi mimo poprawki
    sources:       tuple[str, ...]    # klucze źródeł, np. ("tickets:90001", …)
    unread:        tuple[str, ...]    # klucze z `must_read` spoza listy źródeł
    read_wanted:   tuple[str, ...]    # klucze z `should_read` na liście źródeł
    read_unwanted: tuple[str, ...]    # klucze z `should_not_read` na liście źródeł
    named:         tuple[str, ...]    # fakty z `should_name` nazwane w wyniku (pierwszy wariant)
    excluded:      tuple[str, ...]    # fakty z `should_exclude` nazwane w uwagach jako wykluczone
    code_calls:    int                # wywołania narzędzi kodu w rozmowie
    retries:       int                # poprawki odpowiedzi od węzła `respond`
    fields:        Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def needless_code(self) -> bool:
        """
        Description:
        Czy model sięgnął po narzędzia kodu w sprawie, w której nie powinien.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.case.should_not_call_code and self.code_calls > 0

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu.

        Example args:
            (brak)

        Example result:
            "NIEPRZECZYTANE: tickets:90003"
        """
        # --- odpowiedź nie do przyjęcia: wyniku nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- znaleziony materiał, którego model nie przeczytał ---
        if self.unread:
            return f"NIEPRZECZYTANE: {', '.join(self.unread)}"

        return "zgodny"
