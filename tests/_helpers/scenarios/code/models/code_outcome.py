import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.code.models.code_case import CodeCase


@dataclasses.dataclass(frozen=True)
class CodeOutcome:
    """Ocena jednej sprawy rozpoznania."""

    case:                   CodeCase         # sprawa, której dotyczy ocena
    rejected:               bool               # `respond` nie przyjął odpowiedzi mimo poprawki
    cause_files:            tuple[str, ...]    # pliki zacytowane jako przyczyna, bez powtórzeń
    unread:                 tuple[str, ...]    # cytowania linii, których model wcześniej nie czytał
    listings:               int                # wywołania spisu katalogu kodu
    missing_in_notes:       tuple[str, ...]    # nazwy, które powinny paść w uwagach, a nie padły
    ruled_out_cause_quoted: bool               # przyczyna wykluczona przez wątek zacytowana mimo to
    retries:                int                # poprawki odpowiedzi od węzła `respond`
    fields:                 Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def missing_causes(self) -> tuple[str, ...]:
        """
        Description:
        Pliki wymagane przez sprawę wśród cytowań przyczyny, których model nie zacytował.

        Example args:
            (brak)

        Example result:
            ("src/lib/Urzad/Szablony/RejestrSzablonow.php",)
        """
        missing = tuple(
            path for path in self.case.must_quote_as_cause if path not in self.cause_files
        )

        return missing

    @property
    def stray_causes(self) -> tuple[str, ...]:
        """
        Description:
        Pliki zacytowane jako przyczyna w sprawie, która nie dopuszcza żadnej przyczyny
        (`must_not_quote_any_cause`): komunikatu nie ma nigdzie, więc każde takie cytowanie
        wskazuje luźno powiązany plik.

        Example args:
            (brak)

        Example result:
            ("src/lib/Urzad/Szablony/RejestrSzablonow.php",)
        """
        return self.cause_files if self.case.must_not_quote_any_cause else ()

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu: „zgodny” albo lista tego, co poszło źle.

        Example args:
            (brak)

        Example result:
            "BEZ PLIKU PRZYCZYNY: src/lib/Urzad/Szablony/RejestrSzablonow.php"
        """
        # --- odpowiedź nie do przyjęcia: wyniku nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        problems = [
            f"{name}: {', '.join(found)}"
            for name, found in (
                ("BEZ PLIKU PRZYCZYNY",           self.missing_causes),
                ("PRZYCZYNA Z LUŹNEGO PLIKU",     self.stray_causes),
                ("CYTOWANIE LINII NIEODCZYTANYCH", self.unread),
            )
            if found
        ]

        return "; ".join(problems) if problems else "zgodny"
