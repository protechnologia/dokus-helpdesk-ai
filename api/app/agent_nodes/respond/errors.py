from app.engine_llm import LLMError


class InvalidAnswerError(Exception):
    """
    Description:
    Ostatnia tura modelu nie jest odpowiedzią, którą graf może przyjąć: sam tekst, odpowiedź
    razem z innym wywołaniem, brak wywołania odpowiedzi albo argumenty, które nie przechodzą
    walidacji.

    Do czego:
    Błąd wewnętrzny węzła `respond` — zgłasza go odczyt odpowiedzi, a `run()` zamienia na
    poprawkę dla modelu albo, gdy poprawka już była, na `RespondError`. Niesie dwie rzeczy:
    komunikat, który czyta model, i `reason`, czyli krótką nazwę rodzaju błędu do logu.

    W `reason` są wyłącznie nasze słowa. Komunikat może cytować wartości argumentów, czyli dane
    klienta, więc nie trafia do logu przebiegu ani na INFO.
    """

    def __init__(
        self,
        reason:  str,  # np. "błędne argumenty"
        message: str,  # np. "Błędne argumenty narzędzia `respond_gate_close`: hint: …"
    ):
        """
        Description:
        Zapamiętuje rodzaj błędu obok komunikatu dla modelu.

        Example args:
            reason="błędne argumenty"
            message="Błędne argumenty narzędzia `respond_gate_close`: verdict: Field required. …"

        Example result:
            InvalidAnswerError z `reason` do logu i komunikatem w `str(error)`
        """
        super().__init__(message)

        self.reason = reason


class RespondError(LLMError):
    """
    Description:
    Model nie oddał odpowiedzi, którą graf może przyjąć, także po jednej poprawce.

    Do czego:
    Dziedziczy po `LLMError`, bo dla wołającego to ta sama sytuacja co awaria modelu: wyniku nie
    ma, a ponowione żądanie może go dać. Trasa oddaje więc 503, a przy bramkach decyduje
    helpdesk (CLAUDE.md -> „Bramki jakości"). Komunikat nazywa narzędzie odpowiedzi i rodzaj
    błędu, nigdy treść odpowiedzi modelu.
    """
