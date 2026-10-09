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
