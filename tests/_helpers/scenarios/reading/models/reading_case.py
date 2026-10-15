import dataclasses

from tests._helpers.scenarios.solution import Fact


@dataclasses.dataclass(frozen=True)
class ReadingCase:
    """Jedna sprawa z zestawu: zgłoszenie, grafy, na których idzie, źródła, które model ma albo
    może przeczytać, fakty, które wynik ma nazwać, i to, czy wolno sięgać po kod. Pole z `must_`
    jest warunkiem testu, pola z `should_` — licznikami w raporcie."""

    case_id:              str               # np. "c01"
    graphs:               tuple[str, ...]   # np. ("search", "suggest_questions")
    phenomenon:           str               # co sprawdza i czego oczekujemy
    text:                 str               # zgłoszenie z `RawTicket.as_thread()`
    must_read:            tuple[str, ...]   # klucze źródeł, np. ("tickets:90001", …)
    should_read:          tuple[str, ...]   # klucze źródeł oczekiwane, np. ("docs:adm-…",)
    should_not_read:      tuple[str, ...]   # klucze źródeł niepożądane
    should_name:          tuple[Fact, ...]  # fakty, które wynik ma nazwać w którymkolwiek polu
    should_exclude:       tuple[Fact, ...]  # fakty nazwane w uwagach jako wykluczone
    should_not_call_code: bool              # np. True — sprawa organizacyjna, kod niepożądany

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "c01 sam objaw, a znalezione karty niosą trzy przyczyny"
        """
        return f"{self.case_id} {self.phenomenon}"
