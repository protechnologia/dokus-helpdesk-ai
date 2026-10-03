from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from app.graph import GraphState, merge_sources
from app.llm import ChatMessage, LLMError
from app.nodes import Node
from app.nodes.agent import FakeAgent, tool_call_turn
from app.nodes.respond import FakeRespond
from app.nodes.run_tools import FakeRunTools
from app.tools import SourceRef


class State(GraphState):
    """Stan grafu z narzędziami wiedzy: pola wspólne plus `sources`."""

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)


class Verdict(BaseModel):
    """Wynik grafu na potrzeby testu atrapy `respond`."""

    verdict: str


SEARCH = tool_call_turn("find_tickets", {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"})


async def test_the_agent_answers_at_once_by_default() -> None:
    """Atrapa bez planu → jedna tura z odpowiedzią, bez narzędzi, i iteracja podbita o jeden."""
    update = await FakeAgent().run(State(input_text="x"))

    assert update["iterations"]            == 1
    assert update["messages"][0].role      == "assistant"
    assert update["messages"][0].tool_calls == []


async def test_the_agent_plays_its_turns_in_order() -> None:
    """Plan „szukaj, potem odpowiedz" → najpierw wywołanie narzędzia, potem odpowiedź; trzecie
    wywołanie to błąd, bo graf zawołał agenta częściej, niż test zakładał."""
    agent  = FakeAgent([SEARCH, ChatMessage(role="assistant", content="Odpowiedź")])
    state  = State(input_text="x")

    first  = await agent.run(state)
    second = await agent.run(state)

    assert first["messages"][0].tool_calls[0].name == "find_tickets"
    assert second["messages"][0].content          == "Odpowiedź"

    with pytest.raises(LLMError):
        await agent.run(state)


async def test_run_tools_answers_every_call_by_its_id() -> None:
    """Tura z wywołaniem narzędzia → jedna wiadomość `tool` z tym samym `call_id` i źródła, jeśli
    je podano."""
    ref   = SourceRef(source="find_tickets", item_id="90001", title="Brak przesyłek", score=0.91)
    state = State(input_text="x", messages=[SEARCH])

    update = await FakeRunTools(result_text="Znalezione zgłoszenia: 1", sources=[ref]).run(state)

    assert [message.call_id for message in update["messages"]] == ["call_1"]
    assert update["messages"][0].content == "Znalezione zgłoszenia: 1"
    assert update["sources"]             == [ref]


async def test_run_tools_without_sources_leaves_the_field_alone() -> None:
    """Atrapa bez źródeł → aktualizacja bez `sources`: graf bez narzędzi wiedzy nie ma tego pola."""
    update = await FakeRunTools().run(State(input_text="x", messages=[SEARCH]))

    assert "sources" not in update


async def test_respond_sets_the_given_output() -> None:
    """Atrapa `respond` → `output` równy wynikowi z konstruktora, a stan zapisany w `calls`."""
    respond = FakeRespond(Verdict(verdict="pass"))

    update = await respond.run(State(input_text="x"))

    assert update["output"] == Verdict(verdict="pass")
    assert len(respond.calls) == 1


@pytest.mark.parametrize(
    "node",
    [FakeAgent(), FakeRunTools(), FakeRespond(Verdict(verdict="pass"))],
    ids=lambda node: node.name,
)
async def test_every_fake_node_logs_one_entry_under_its_name(node: Node) -> None:
    """Wywołanie atrapy węzła → dokładnie jeden wpis w `log`, podpisany nazwą węzła."""
    update = await node.run(State(input_text="x", messages=[SEARCH]))

    assert [entry.node for entry in update["log"]] == [node.name]


async def test_the_agent_logs_which_tools_it_called() -> None:
    """Tura z wywołaniem narzędzia → wpis w logu nazywa narzędzie, nie cytuje argumentów."""
    update = await FakeAgent([SEARCH]).run(State(input_text="x"))

    assert update["log"][0].message == "tura 1: narzędzia: find_tickets"
