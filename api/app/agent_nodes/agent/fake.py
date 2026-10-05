from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.agent_nodes.agent.base import AgentNodeBase
from app.engine_llm import ChatMessage, LLMError, LLMUsage, ToolCall

# Odpowiedź atrapy, gdy nikt nie zaplanował tur — stała, a nie echo wejścia, żeby test, który
# przypadkiem na niej polega, padł głośno.
DEFAULT_ANSWER = "fake-agent-answer"


def tool_call_turn(
    name:      str,             # np. "find_tickets_vector"
    arguments: dict[str, Any],  # np. {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}
    call_id:   str = "call_1",  # np. "call_2"
) -> ChatMessage:
    """
    Description:
    Buduje turę modelu z jednym wywołaniem narzędzia — do zaplanowania w `FakeAgentNode`.

    Example args:
        name="find_tickets_vector"
        arguments={"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}

    Example result:
        ChatMessage(role="assistant", tool_calls=[ToolCall(name="find_tickets_vector", …)])
    """
    turn = ChatMessage(
        role       = "assistant",
        tool_calls = [ToolCall(call_id=call_id, name=name, arguments=arguments)],
    )

    return turn


class FakeAgentNode(AgentNodeBase):
    """
    Description:
    Atrapa węzła `agent`: zamiast pytać model, oddaje zaplanowane tury po kolei. Domyślnie jedna
    tura — sam tekst, bez narzędzi.

    Flow:
        1. Test tworzy ją z listą tur (np. najpierw `tool_call_turn(…)`, potem odpowiedź).
        2. Każde `run()` zapisuje stan w `calls` i oddaje kolejną turę tą samą zmianą stanu co
           węzeł właściwy (`turn_update()`); zużycie jednej tury to domyślnie jedno wywołanie
           bez tokenów i kosztu, bo atrapa niczego nie wysyła.
        3. Brak kolejnej tury to błąd, nie powtórka: graf zawołał agenta częściej, niż test
           zakładał.

    Tury użytkownika atrapa nie dokłada — nie zna promptu grafu — więc `messages` po przebiegu na
    atrapie zaczynają się od tury modelu.
    """

    def __init__(
        self,
        turns: Sequence[ChatMessage] | None = None,  # np. [tool_call_turn(…), ChatMessage(…)]
        usage: LLMUsage | None = None,               # np. LLMUsage(calls=1, cost_usd=0.02)
    ):
        """
        Description:
        Ustala tury, które atrapa odda, zużycie modelu zgłaszane przy każdej z nich i zakłada
        dziennik wywołań.

        Example args:
            turns=[tool_call_turn("find_tickets_vector", {…}),
                   ChatMessage(role="assistant", content="…")]
            usage=LLMUsage(calls=1, prompt_tokens=5000, completion_tokens=100, cost_usd=0.02)

        Example result:
            FakeAgentNode oddająca te dwie tury po kolei, każdą za 0.02 USD
        """
        default_turn = ChatMessage(role="assistant", content=DEFAULT_ANSWER)

        self._turns: list[ChatMessage] = list(turns) if turns is not None else [default_turn]
        self._next:  int               = 0

        # Atrapa nie woła modelu: jedna tura to jedno wywołanie, zero tokenów i zero kosztu.
        self._usage: LLMUsage = usage if usage is not None else LLMUsage(calls=1)

        # Publiczne celowo: testy sprawdzają, z jakim stanem agent był wołany.
        self.calls: list[BaseModel] = []

    async def run(
        self,
        state: BaseModel,  # np. stan grafu z messages=[…], iterations=0
    ) -> dict[str, Any]:
        """
        Description:
        Oddaje kolejną zaplanowaną turę i podbija licznik iteracji.

        Example args:
            state=SuggestSolutionState(input_text="…", iterations=0)

        Example result:
            {"messages": [ChatMessage(role="assistant", …)], "iterations": 1,
             "usage": LLMUsage(calls=1),
             "log": [LogEntry(node="agent", message="tura 1: tekst bez narzędzi")]}

        Raises:
            LLMError: zaplanowane tury się skończyły
        """
        self.calls.append(state)

        if self._next >= len(self._turns):
            raise LLMError(f"FakeAgentNode: skończyły się zaplanowane tury ({len(self._turns)})")

        turn = self._turns[self._next]
        self._next += 1

        return self.turn_update(state=state, messages=[turn], usage=self._usage)
