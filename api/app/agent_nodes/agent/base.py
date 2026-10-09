from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.agent_nodes.base import Node
from app.engine_llm import ChatMessage, LLMUsage


class AgentNodeBase(Node):
    """
    Description:
    To, co wspólne dla węzła `agent` i jego atrapy: nazwa i zapis tury modelu w stanie grafu.
    Węzeł i atrapa różnią się wyłącznie tym, skąd biorą turę — z modelu albo z planu testu —
    więc test na atrapie widzi ten sam licznik tur i ten sam wpis w logu co przebieg z modelem.
    """

    name = "agent"

    def turn_update(
        self,
        state:    BaseModel,              # stan grafu przed turą, np. SearchState(iterations=0, …)
        messages: Sequence[ChatMessage],  # nowe wiadomości; ostatnia to tura modelu
        usage:    LLMUsage,               # zużycie modelu w tej turze, np. LLMUsage(calls=1)
    ) -> dict[str, Any]:
        """
        Description:
        Składa zmianę stanu po jednej turze modelu: nowe wiadomości, licznik tur podbity o jeden,
        zużycie tej tury i wpis w logu. W logu są nazwy wywołanych narzędzi i koszt tury —
        argumenty i tekst modelu to dane klienta.

        Koszt we wpisie jest dla czytającego człowieka: widać, która tura ile kosztowała. Do
        liczenia służy `usage`, które graf sumuje po turach; z tekstu logu nikt liczb nie
        wyciąga.

        Example args:
            state=SearchState(input_text="…", iterations=0)
            messages=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="read_docs", …)])]
            usage=LLMUsage(calls=1, prompt_tokens=4820, cost_usd=0.0321)

        Example result:
            {"messages": [ChatMessage(role="assistant", …)], "iterations": 1,
             "usage": LLMUsage(calls=1, prompt_tokens=4820, cost_usd=0.0321),
             "log": [LogEntry(node="agent", message="tura 1: narzędzia: read_docs; 0,0321 USD")]}
        """
        iteration = state.iterations + 1
        tools     = ", ".join(call.name for call in messages[-1].tool_calls)
        action    = f"narzędzia: {tools}" if tools else "tekst bez narzędzi"
        # Przecinek dziesiętny, bo wpis to polski tekst; liczba z kropką stoi w `usage`.
        cost      = f"{usage.cost_usd:.4f}".replace(".", ",")

        update = {
            "messages":   list(messages),
            "iterations": iteration,
            "usage":      usage,
            "log":        [self.log_entry(f"tura {iteration}: {action}; {cost} USD")],
        }

        return update
