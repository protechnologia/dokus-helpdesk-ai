import dataclasses

from tests._helpers.scenarios.code.models.code_fragment import CodeFragment


@dataclasses.dataclass(frozen=True)
class CodeCase:
    """Jedna sprawa cytowania kodu z zestawu: zgłoszenie, materiał atrap i to, co ma z niej wyjść.
    Pola z `must_` są warunkami testu, pola z `should_` — licznikami w raporcie."""

    case_id:                   str                  # np. "k01"
    phenomenon:                str                  # co sprawa sprawdza — czego oczekujemy
    text:                      str                  # zgłoszenie w kształcie `RawTicket.as_thread()`
    finds_tickets_and_docs:    bool                 # szukanie zgłoszeń i instrukcji coś znajduje
    must_quote_as_cause:       tuple[str, ...]      # pliki, które muszą być wśród przyczyn
    must_not_quote_any_cause:  bool                 # żadnego cytowania przyczyny
    notes_should_include:      tuple[str, ...]      # nazwy, które powinny paść w uwagach
    should_not_quote_as_cause: CodeFragment | None  # przyczyna wykluczona przez klienta

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "k01 komunikat o nadmiarowym szablonie stoi tylko w kodzie — model cytuje …"
        """
        return f"{self.case_id} {self.phenomenon}"
