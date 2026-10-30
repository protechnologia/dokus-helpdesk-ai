import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.handoff.models.handoff_case import HandoffCase


@dataclasses.dataclass(frozen=True)
class HandoffOutcome:
    """Ocena wiadomości z jednej sprawy przekazania."""

    case:         HandoffCase        # sprawa, której dotyczy ocena
    rejected:     bool               # węzeł `respond` nie przyjął odpowiedzi mimo poprawki
    layout:       tuple[str, ...]    # to, czym układ różni się od przykładu
    lost:         tuple[str, ...]    # fakty z wątku, których w wiadomości nie ma
    warning_lost: bool               # wątek ostrzega, a wiadomość tego nie powtarza
    new_numbers:  tuple[str, ...]    # liczby z wiadomości, których nie ma w wątku
    added:        tuple[str, ...]    # pułapki, które trafiły do wiadomości
    promised:     tuple[str, ...]    # obietnice działania w wiadomości
    copied:       tuple[str, ...]    # fragmenty przykładu z opisu pola `text` w wiadomości
    malformed:    tuple[str, ...]    # napisy w klamrach spoza znaczników i placeholderów
    retries:      int                # poprawki odpowiedzi od węzła `respond`
    fields:       Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu: „zgodny” albo lista tego, co poszło źle.

        Example args:
            (brak)

        Example result:
            "zgubione: UPO; obietnice: sprawdzimy"
        """
        # --- odpowiedź nie do przyjęcia: wiadomości nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        problems = [
            f"{name}: {', '.join(found)}"
            for name, found in (
                ("układ",                 self.layout),
                ("zgubione",              self.lost),
                ("zgubione ostrzeżenie",  self.case.warning[:1] if self.warning_lost else ()),
                ("nowe liczby",           self.new_numbers),
                ("dopisane",              self.added),
                ("obietnice",             self.promised),
                ("z przykładu",           self.copied),
                ("przekręcone znaczniki", self.malformed),
            )
            if found
        ]

        return "; ".join(problems) if problems else "zgodny"
