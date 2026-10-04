from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent_nodes.base import Node
from app.agent_nodes.run_tools.limits import calls_over_limit, limit_exceeded_text
from app.agent_tools import SourceRef
from app.engine_llm import ChatMessage

DEFAULT_TOOL_RESULT = "fake-tool-result"


class FakeToolAnswer(BaseModel):
    """
    Description:
    Co atrapa `run_tools` odpowiada na wywołanie jednego narzędzia: tekst wyniku i źródła, które
    to wywołanie dokłada. Wyszukiwanie odpowiada samym tekstem, odczyt — tekstem i źródłami.
    """

    model_config = ConfigDict(extra="forbid")

    text:    str             = Field(examples=['{"tickets": [{"ticket_id": "90001", …}]}'])
    sources: list[SourceRef] = Field(default_factory=list)


class FakeRunToolsNode(Node):
    """
    Description:
    Atrapa węzła `run_tools`: nie woła narzędzi, tylko na każde wywołanie z ostatniej tury modelu
    odpowiada ustalonym tekstem i — jeśli je podano — dokłada ustalone źródła.

    Flow:
        1. Test tworzy ją z odpowiedzią domyślną (tekst i opcjonalne źródła) albo z odpowiedziami
           na konkretne narzędzia (`answers`) — tak odtwarza się przebieg „szukaj, potem czytaj",
           w którym źródła dokłada dopiero odczyt.
        2. `run()` zapisuje stan w `calls` i zwraca po jednej wiadomości `tool` na każde
           wywołanie, z jego `call_id`.
        3. Wywołanie ponad limit swojego narzędzia (`limits`) dostaje błąd zamiast odpowiedzi
           i nie dokłada źródeł — tą samą regułą, którą stosuje węzeł właściwy (`limits.py`).
        4. `sources` trafiają do aktualizacji tylko wtedy, gdy wywołane narzędzia je dokładają —
           graf bez narzędzi wiedzy nie ma tego pola w stanie.
    """

    name = "run_tools"

    def __init__(
        self,
        result_text: str = DEFAULT_TOOL_RESULT,                   # np. '{"tickets": []}'
        sources:     Sequence[SourceRef] = (),                    # np. [SourceRef(…)]
        answers:     Mapping[str, FakeToolAnswer] | None = None,  # np. {"read_docs": …}
        limits:      Mapping[str, int] | None = None,             # np. {"read_docs": 2}
    ):
        """
        Description:
        Ustala, co atrapa odpowie: `answers` na wymienione narzędzia, a `result_text`
        i `sources` na każde inne. `limits` to limity wywołań narzędzi w jednym przebiegu;
        bez nich atrapa niczego nie odmawia.

        Example args:
            result_text='{"tickets": []}'
            sources=[]
            answers={"read_tickets_card": FakeToolAnswer(text="{…}", sources=[SourceRef(…)])}
            limits={"read_tickets_card": 3}

        Example result:
            FakeRunToolsNode odpowiadająca kartami na odczyt i pustym wynikiem na resztę
        """
        self._default = FakeToolAnswer(text=result_text, sources=list(sources))
        self._answers = dict(answers or {})
        self._limits  = dict(limits or {})

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
            state=SuggestSolutionState(messages=[tool_call_turn("read_tickets_card", {…})], …)

        Example result:
            {"messages": [ChatMessage(role="tool", call_id="call_1", content="…")],
             "log": [LogEntry(node="run_tools",
                              message="wywołania: read_tickets_card; źródła: 1")],
             "sources": [SourceRef(…)]}
        """
        self.calls.append(state)

        calls   = state.messages[-1].tool_calls if state.messages else []
        names   = ", ".join(call.name for call in calls) or "brak"
        refused = calls_over_limit(state.messages, self._limits)

        # Wywołanie ponad limit dostaje błąd i nie dokłada źródeł; pozostałe swoją odpowiedź.
        answers = [
            FakeToolAnswer(text=limit_exceeded_text(call.name, self._limits[call.name]))
            if call.call_id in refused
            else self._answers.get(call.name, self._default)
            for call in calls
        ]

        results = [
            ChatMessage(role="tool", call_id=call.call_id, content=answer.text)
            for call, answer in zip(calls, answers, strict=True)
        ]
        sources = [ref for answer in answers for ref in answer.sources]

        # Same nazwy i liczby — treść wyników to dane klienta.
        summary = f"wywołania: {names}; źródła: {len(sources)}"

        if refused:
            summary += f"; ponad limit: {len(refused)}"

        update: dict[str, Any] = {
            "messages": results,
            "log":      [self.log_entry(summary)],
        }

        if sources:
            update["sources"] = sources

        return update
