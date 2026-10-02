from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from app.nodes.models import LogEntry


class Node(ABC):
    """
    Description:
    Jeden krok grafu: czyta stan i zwraca pola, które zmienia.

    Do czego:
    Wspólny kontrakt węzłów — właściwych i atrap — żeby każdy graf składał je tak samo
    (`graph.add_node(node.name, node.run)`) i żeby test grafów (p. 12) rozpoznawał je po nazwie,
    np. czy pierwszym węzłem jest `anonymize`.

    Stan to model z `state.py` konkretnego grafu, dziedziczący po `GraphState` (`app/graph/base.py`)
    — stąd pola, które czyta każdy węzeł (`input_text`, `messages`, `iterations`, `log`). Pola
    własne grafu (np. `sources`) czyta tylko węzeł, który ich potrzebuje.
    """

    # Nazwa węzła w grafie.
    name: ClassVar[str]

    @abstractmethod
    async def run(
        self,
        state: BaseModel,  # np. SuggestSolutionState(input_text="Nie przychodzą przesyłki…")
    ) -> dict[str, Any]:
        """
        Description:
        Wykonuje krok i zwraca wyłącznie zmieniane pola stanu. Dla list (`messages`, `sources`,
        `log`) — tylko nowe elementy, bo doklejają je reduktory z adnotacji pól. Każde wywołanie
        dopisuje jeden wpis do `log` (`log_entry()`).

        Example args:
            state=SuggestSolutionState(input_text="Nie przychodzą przesyłki z e-Doręczeń")

        Example result:
            {"anonymized": AnonymizedText(text="Nie przychodzą przesyłki z e-Doręczeń"),
             "log": [LogEntry(node="anonymize", message="zanonimizowano 37 zn.")]}
        """

    def log_entry(
        self,
        message: str,  # np. "tura 1: odpowiedź bez narzędzi"
    ) -> LogEntry:
        """
        Description:
        Buduje wpis do `log` podpisany nazwą tego węzła. Bez treści zgłoszenia i odpowiedzi
        modelu — tylko nazwy, liczby i identyfikatory (patrz `LogEntry`).

        Example args:
            message="tura 1: odpowiedź bez narzędzi"

        Example result:
            LogEntry(node="agent", message="tura 1: odpowiedź bez narzędzi")
        """
        return LogEntry(node=self.name, message=message)
