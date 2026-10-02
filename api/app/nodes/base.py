from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel


class Node(ABC):
    """
    Description:
    Jeden krok grafu: czyta stan i zwraca pola, które zmienia.

    Do czego:
    Wspólny kontrakt węzłów — właściwych i atrap — żeby każdy graf składał je tak samo
    (`graph.add_node(node.name, node.run)`) i żeby test grafów (p. 12) rozpoznawał je po nazwie,
    np. czy pierwszym węzłem jest `anonymize`.

    Stan to model z `state.py` konkretnego grafu — wspólnej klasy stanu nie ma. Węzeł czyta pola,
    których potrzebuje (np. `messages`, `sources`), więc graf, który go używa, musi je mieć.
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
        Wykonuje krok i zwraca wyłącznie zmieniane pola stanu. Dla list (`messages`, `sources`)
        — tylko nowe elementy, bo doklejają je reduktory z adnotacji pól.

        Example args:
            state=SuggestSolutionState(input_text="Nie przychodzą przesyłki z e-Doręczeń")

        Example result:
            {"anonymized": AnonymizedText(text="Nie przychodzą przesyłki z e-Doręczeń")}
        """
