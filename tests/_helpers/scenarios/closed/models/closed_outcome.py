import dataclasses
from collections.abc import Mapping
from typing import Any

from tests._helpers.scenarios.closed.models.closed_case import ClosedCase

# Wyniki, przy których bramka przepuściła zamknięcie: karta powstała i ocenił ją filtr.
PASSED = ("indexed", "dropped")


@dataclasses.dataclass(frozen=True)
class ClosedOutcome:
    """Ocena odpowiedzi trasy zamknięcia na jedną sprawę."""

    case:   ClosedCase         # sprawa, której dotyczy ocena
    status: int                # kod HTTP odpowiedzi, np. 200
    answer: str | None         # `outcome` z odpowiedzi, np. "indexed"; None — kod inny niż 200
    fields: Mapping[str, Any]  # pola odpowiedzi do raportu; puste, gdy odpowiedź nie przyszła

    @property
    def failed(self) -> bool:
        """
        Description:
        Czy trasa nie oddała wyniku: awaria modelu albo odpowiedź, której węzeł `respond` nie
        przyjął (503), albo błąd w kodzie (500).

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer is None

    @property
    def false_block(self) -> bool:
        """
        Description:
        Czy bramka zablokowała zamknięcie, z którego wynika problem i to, co zrobiono.

        Example args:
            (brak)

        Example result:
            True
        """
        return self.answer == "blocked" and self.case.expected in PASSED

    @property
    def missed_block(self) -> bool:
        """
        Description:
        Czy bramka przepuściła zamknięcie, którego powinna była zatrzymać, więc karta powstała.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.answer in PASSED and self.case.expected == "blocked"

    @property
    def wrong_filter(self) -> bool:
        """
        Description:
        Czy po przepuszczeniu przez bramkę filtr zdecydował inaczej, niż wymaga sprawa: odrzucił
        kartę z wiedzą albo wpuścił do indeksów kartę bez wiedzy.

        Example args:
            (brak)

        Example result:
            False
        """
        return (
            self.answer in PASSED
            and self.case.expected in PASSED
            and self.answer != self.case.expected
        )

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym słowem albo kilkoma dla raportu.

        Example args:
            (brak)

        Example result:
            "ZABLOKOWANE BEZ POWODU"
        """
        # --- trasa nie oddała wyniku ---
        if self.failed:
            return f"BŁĄD TRASY (kod {self.status})"

        # --- dobre zamknięcie zatrzymane przez bramkę ---
        if self.false_block:
            return "ZABLOKOWANE BEZ POWODU"

        # --- puste zamknięcie przepuszczone przez bramkę ---
        if self.missed_block:
            return "PRZEPUSZCZONE PRZEZ BRAMKĘ"

        # --- filtr przy karcie zdecydował odwrotnie ---
        if self.wrong_filter:
            return "FILTR ZDECYDOWAŁ INACZEJ"

        return "zgodny"
