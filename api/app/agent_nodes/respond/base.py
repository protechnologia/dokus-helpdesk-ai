from typing import Any

from pydantic import BaseModel

from app.agent_nodes.base import Node


class RespondNodeBase(Node):
    """
    Description:
    To, co wspólne dla węzła `respond` i jego atrapy: nazwa i zapis wyniku w stanie grafu. Węzeł
    i atrapa różnią się wyłącznie tym, skąd biorą wynik — z odpowiedzi modelu albo z ustaleń
    testu — więc test na atrapie widzi to samo pole `output` i ten sam wpis w logu co przebieg
    z modelem.
    """

    name = "respond"

    def output_update(
        self,
        output: BaseModel,  # np. Verdict(verdict="pass", reasons=[], missing=[], hint="")
    ) -> dict[str, Any]:
        """
        Description:
        Składa zmianę stanu po przyjęciu odpowiedzi: wynik grafu i wpis w logu. W logu jest sama
        nazwa typu wyniku — jego treść to odpowiedź modelu, czyli dane klienta.

        Example args:
            output=Verdict(verdict="pass")

        Example result:
            {"output": Verdict(verdict="pass", …),
             "log": [LogEntry(node="respond", message="output: Verdict")]}
        """
        update = {
            "output": output,
            "log":    [self.log_entry(f"output: {type(output).__name__}")],
        }

        return update
