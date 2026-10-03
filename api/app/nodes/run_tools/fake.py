from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.llm import ChatMessage
from app.nodes.base import Node
from app.tools import SourceRef

DEFAULT_TOOL_RESULT = "fake-tool-result"


class FakeRunToolsNode(Node):
    """
    Description:
    Atrapa węzła `run_tools`: nie woła narzędzi, tylko na każde wywołanie z ostatniej tury modelu
    odpowiada tym samym tekstem i — jeśli je podano — dokłada ustalone źródła.

    Flow:
        1. Test tworzy ją z tekstem wyniku i opcjonalnymi źródłami.
        2. `run()` zapisuje stan w `calls` i zwraca po jednej wiadomości `tool` na każde
           wywołanie, z jego `call_id`.
        3. `sources` trafiają do aktualizacji tylko wtedy, gdy podano źródła — graf bez narzędzi
           wiedzy nie ma tego pola w stanie.
    """

    name = "run_tools"

    def __init__(
        self,
        result_text: str = DEFAULT_TOOL_RESULT,  # np. "Znalezione zgłoszenia: 3 …"
        sources:     Sequence[SourceRef] = (),   # np. [SourceRef(source="tickets", …)]
    ):
        """
        Description:
        Ustala tekst wyniku i źródła, które atrapa odda.

        Example args:
            result_text="Znalezione zgłoszenia: 3"
            sources=[SourceRef(source="tickets", item_id="90001", …)]

        Example result:
            FakeRunToolsNode odpowiadająca tym tekstem na każde wywołanie
        """
        self._result_text = result_text
        self._sources     = list(sources)

        # Publiczne celowo: testy sprawdzają, z jakim stanem węzeł był wołany.
        self.calls: list[BaseModel] = []

    async def run(
        self,
        state: BaseModel,  # np. stan grafu, którego ostatnia wiadomość zleca narzędzia
    ) -> dict[str, Any]:
        """
        Description:
        Odpowiada na wywołania narzędzi z ostatniej tury modelu.

        Example args:
            state=SuggestSolutionState(messages=[tool_call_turn("find_tickets_vector", {…})], …)

        Example result:
            {"messages": [ChatMessage(role="tool", call_id="call_1", content="…")],
             "log": [LogEntry(node="run_tools",
                              message="wywołania: find_tickets_vector; źródła: 1")],
             "sources": [SourceRef(…)]}
        """
        self.calls.append(state)

        calls   = state.messages[-1].tool_calls if state.messages else []
        names   = ", ".join(call.name for call in calls) or "brak"
        results = [
            ChatMessage(role="tool", call_id=call.call_id, content=self._result_text)
            for call in calls
        ]

        update: dict[str, Any] = {
            "messages": results,
            "log":      [self.log_entry(f"wywołania: {names}; źródła: {len(self._sources)}")],
        }

        if self._sources:
            update["sources"] = list(self._sources)

        return update
