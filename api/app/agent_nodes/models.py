from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """
    Description:
    Jeden wpis w `log` stanu grafu: który węzeł co zrobił w tym wywołaniu.

    Do czego:
    Przebieg grafu do odczytania po fakcie — kolejność węzłów, liczba tur, wywołane narzędzia —
    bez zewnętrznego tracingu (LangSmith jest zablokowany). Każdy węzeł dopisuje jeden wpis na
    wywołanie przez `Node.log_entry()`.

    `message` niesie wyłącznie nazwy, liczby i identyfikatory, nigdy treści zgłoszenia ani
    odpowiedzi modelu: log wraca w stanie razem z wynikiem i trafia tam, gdzie dane klienta nie
    mają prawa trafić (CLAUDE.md -> „Logi i obserwowalność").
    """

    model_config = ConfigDict(extra="forbid")

    node:    str = Field(min_length=1, examples=["agent"])
    message: str = Field(min_length=1, examples=["tura 1: narzędzia: read_docs; 0,0041 USD"])


class ToolTiming(BaseModel):
    """
    Description:
    Czas jednego wywołania narzędzia w węźle `run_tools`: kiedy się zaczęło i ile trwało.
    Wywołanie wskazuje `call_id`, ten sam co w turze modelu i w wiadomości `tool` z wynikiem.

    Do czego:
    Krok narzędzi trwa tyle, ile wszystkie jego wywołania razem, bo idą po kolei; dopiero czas na
    wywołanie pokazuje, które narzędzie zajęło sprawie najwięcej. Mierzy go węzeł, bo tylko on
    widzi początek i koniec każdego wywołania. Czas ma każde wywołanie, także odrzucone limitem
    albo błędem, więc każda wiadomość `tool` z tego kroku ma swój pomiar.
    """

    model_config = ConfigDict(extra="forbid")

    call_id:     str      = Field(min_length=1, examples=["call_1"])
    started_at:  datetime = Field(examples=["2026-10-19T12:03:15.120000Z"])
    duration_ms: float    = Field(ge=0, examples=[84.2])
