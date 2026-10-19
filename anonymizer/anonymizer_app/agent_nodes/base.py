from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from anonymizer_app.core_model.log_entry import LogEntry


class Node(ABC):
    """
    Description:
    Jeden krok grafu anonimizacji: czyta stan i zwraca pola, które zmienia.

    Do czego:
    Wspólny kontrakt węzłów, żeby graf składał je tak samo (`graph.add_node(node.name,
    node.run)`). Ten sam kształt co węzły grafów w `api`, ale kodu z nimi usługa nie dzieli.

    Stan to `AnonymizeState` (`agent_graphs/anonymize/state.py`); węzeł czyta tylko pola, których
    potrzebuje.
    """

    # Nazwa węzła w grafie, zarazem nazwa jego katalogu.
    name: ClassVar[str]

    @abstractmethod
    async def run(
        self,
        state: BaseModel,  # np. AnonymizeState(input_text="Od: Bogumił Cieślak…")
    ) -> dict[str, Any]:
        """
        Description:
        Wykonuje krok i zwraca wyłącznie zmieniane pola stanu, z jednym nowym wpisem w `log`
        (`log_entry()`); reduktor pola dokleja go do wpisów wcześniejszych węzłów.

        Example args:
            state=AnonymizeState(input_text="PESEL 85030512840")

        Example result:
            {"after_patterns": "PESEL {PESEL}",
             "log": [LogEntry(node="replace_patterns", message="1 miejsc: PESEL 1")]}
        """

    def log_entry(
        self,
        message: str,  # np. "7 fragmentów → 19 miejsc"
    ) -> LogEntry:
        """
        Description:
        Buduje wpis przebiegu podpisany nazwą tego węzła. Bez tekstu i fragmentów — tylko nazwy
        rodzajów i liczby (patrz `LogEntry`).

        Example args:
            message="7 fragmentów → 19 miejsc"

        Example result:
            LogEntry(node="find_persons", message="7 fragmentów → 19 miejsc")
        """
        return LogEntry(node=self.name, message=message)
