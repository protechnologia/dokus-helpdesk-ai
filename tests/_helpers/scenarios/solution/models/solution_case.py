import dataclasses
from collections.abc import Mapping
from typing import Any

# Fakt: warianty brzmienia; stoi w tekście, gdy stoi w nim którykolwiek wariant.
Fact = tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class SolutionCase:
    """Jedna sprawa z zestawu: zgłoszenie, zmiany wbudowanych kart atrap i fakty, które mają albo
    nie mają stać w treści dla klienta. Pola z `must_` są warunkami testu, pola z `should_` —
    licznikami w raporcie."""

    case_id:            str                              # np. "r03"
    phenomenon:         str                              # co sprawdza i czego oczekujemy
    text:               str                              # zgłoszenie z `RawTicket.as_thread()`
    card_changes:       Mapping[str, Mapping[str, Any]]  # {numer karty: {pole: nowa wartość}}
    must_mention:       tuple[Fact, ...]                 # każdy fakt musi stać w treści
    should_mention:     tuple[Fact, ...]                 # oczekiwane: wszystkie fakty naraz
    should_not_mention: tuple[Fact, ...]                 # niepożądane: wszystkie fakty naraz

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "r03 karta 90002 z krokiem nieodwracalnym — treść dla klienta niesie …"
        """
        return f"{self.case_id} {self.phenomenon}"
