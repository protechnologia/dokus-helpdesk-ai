from typing import Any

from pydantic import BaseModel

from app.nodes.base import Node


class FakeRespond(Node):
    """
    Description:
    Atrapa węzła `respond`: nie waliduje odpowiedzi modelu, tylko ustawia `output` na wynik podany
    w konstruktorze — w typie, którego oczekuje stan danego grafu (`Verdict`, propozycja…).

    Flow:
        1. Test (albo atrapa grafu) tworzy ją z gotowym wynikiem.
        2. `run()` zapisuje stan w `calls` i zwraca ten wynik jako `output`.
    """

    name = "respond"

    def __init__(
        self,
        output: BaseModel,  # np. Verdict(verdict="pass", reasons=[], missing=[], hint="")
    ):
        """
        Description:
        Ustala wynik, który atrapa wstawi do stanu.

        Example args:
            output=Verdict(verdict="pass", …)

        Example result:
            FakeRespond zwracająca ten wynik przy każdym wywołaniu
        """
        self._output = output

        # Publiczne celowo: testy sprawdzają, z jakim stanem węzeł był wołany.
        self.calls: list[BaseModel] = []

    async def run(
        self,
        state: BaseModel,  # np. stan grafu po ostatniej turze modelu
    ) -> dict[str, Any]:
        """
        Description:
        Ustawia `output` na zadany wynik.

        Example args:
            state=GateCloseState(input_text="…", messages=[…])

        Example result:
            {"output": Verdict(verdict="pass", …)}
        """
        self.calls.append(state)

        return {"output": self._output}
