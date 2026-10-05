from collections.abc import Sequence
from typing import Any

from app.agent_nodes.base import Node
from app.agent_tools import SourceRef
from app.engine_llm import ChatMessage, ToolCall


class RunToolsNodeBase(Node):
    """
    Description:
    To, co wspólne dla węzła `run_tools` i jego atrapy: nazwa i zapis odpowiedzi narzędzi
    w stanie grafu. Węzeł i atrapa różnią się wyłącznie tym, skąd biorą odpowiedź na wywołanie —
    z narzędzia albo z ustaleń testu — więc test na atrapie widzi te same wiadomości `tool` i ten
    sam wpis w logu co przebieg z narzędziami.
    """

    name = "run_tools"

    def results_update(
        self,
        calls:      Sequence[ToolCall],   # wywołania z ostatniej tury modelu
        texts:      Sequence[str],        # co model dostaje na każde z nich, w tej samej kolejności
        sources:    Sequence[SourceRef],  # źródła z odczytów wykonanych w tej turze
        over_limit: int = 0,              # ile wywołań dostało odmowę z powodu limitu
        failed:     int = 0,              # ile wywołań dostało inny błąd zamiast wyniku
    ) -> dict[str, Any]:
        """
        Description:
        Składa zmianę stanu po wykonaniu narzędzi: po jednej wiadomości `tool` na wywołanie,
        z jego `call_id`, źródła z odczytów i wpis w logu. W logu są same nazwy narzędzi
        i liczby — argumenty i wyniki to dane klienta. `sources` trafiają do zmiany tylko wtedy,
        gdy są: stan grafu bez narzędzi wiedzy nie ma tego pola.

        Example args:
            calls=[ToolCall(call_id="call_2", name="read_tickets_card", arguments={…})]
            texts=['{"cards": [{"ticket_id": "90001", …}], "without_card": []}']
            sources=[SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…")]
            over_limit=0
            failed=0

        Example result:
            {"messages": [ChatMessage(role="tool", call_id="call_2", content='{"cards": […]}')],
             "log": [LogEntry(node="run_tools",
                              message="wywołania: read_tickets_card; źródła: 1")],
             "sources": [SourceRef(source="tickets", item_id="90001", …)]}
        """
        results = [
            ChatMessage(role="tool", call_id=call.call_id, content=text)
            for call, text in zip(calls, texts, strict=True)
        ]

        # --- wpis w logu: nazwy i liczby ---
        names   = ", ".join(call.name for call in calls) or "brak"
        summary = f"wywołania: {names}; źródła: {len(sources)}"

        if over_limit:
            summary += f"; ponad limit: {over_limit}"

        if failed:
            summary += f"; błędy: {failed}"

        update: dict[str, Any] = {
            "messages": results,
            "log":      [self.log_entry(summary)],
        }

        if sources:
            update["sources"] = list(sources)

        return update
