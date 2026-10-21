import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.polish.models.polish_case import PolishCase


@dataclasses.dataclass(frozen=True)
class PolishOutcome:
    """Ocena jednej sprawy „Popraw”."""

    case:         PolishCase              # sprawa, której dotyczy ocena
    rejected:     bool                    # węzeł `respond` nie przyjął odpowiedzi mimo poprawki
    colloquial:   tuple[str, ...]         # słowa potoczne, które zostały w tekście
    lost:         tuple[str, ...]         # fakty z notatek, których w tekście nie ma
    new_numbers:  tuple[str, ...]         # liczby z tekstu, których nie ma w notatkach
    added:        tuple[str, ...]         # pułapki, które trafiły do tekstu
    retries:      int                     # poprawki odpowiedzi od węzła `respond`
    fields:       Mapping[str, Any]       # pola wyniku do raportu; puste, gdy wyniku nie ma
    lost_markers: tuple[str, ...] = ()    # znaczniki z notatek, których w tekście jest mniej
    malformed:    tuple[str, ...] = ()    # napisy w klamrach spoza znaczników i placeholderów

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu: „zgodny” albo lista tego, co poszło źle.

        Example args:
            (brak)

        Example result:
            "potoczne: smig; nowe liczby: 3"
        """
        # --- odpowiedź nie do przyjęcia: tekstu nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        problems = [
            f"{name}: {', '.join(found)}"
            for name, found in (
                ("potoczne",              self.colloquial),
                ("zgubione",              self.lost),
                ("nowe liczby",           self.new_numbers),
                ("dopisane",              self.added),
                ("zgubione znaczniki",    self.lost_markers),
                ("przekręcone znaczniki", self.malformed),
            )
            if found
        ]

        return "; ".join(problems) if problems else "zgodny"
