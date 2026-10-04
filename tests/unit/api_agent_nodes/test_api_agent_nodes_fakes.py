import json
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from app.agent_graphs import GraphState, merge_sources
from app.agent_nodes import Node
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode, FakeToolAnswer
from app.agent_tools import SourceRef
from app.engine_llm import ChatMessage, LLMError


class State(GraphState):
    """Stan grafu z narzędziami wiedzy: pola wspólne plus `sources`."""

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)


class Verdict(BaseModel):
    """Wynik grafu na potrzeby testu atrapy `respond`."""

    verdict: str


SEARCH = tool_call_turn(
    "find_tickets_vector",
    {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"},
)


async def test_the_agent_answers_at_once_by_default() -> None:
    """Atrapa bez planu → jedna tura z odpowiedzią, bez narzędzi, i iteracja podbita o jeden."""
    update = await FakeAgentNode().run(State(input_text="x"))

    assert update["iterations"]            == 1
    assert update["messages"][0].role      == "assistant"
    assert update["messages"][0].tool_calls == []


async def test_the_agent_plays_its_turns_in_order() -> None:
    """Plan „szukaj, potem odpowiedz" → najpierw wywołanie narzędzia, potem odpowiedź; trzecie
    wywołanie to błąd, bo graf zawołał agenta częściej, niż test zakładał."""
    agent  = FakeAgentNode([SEARCH, ChatMessage(role="assistant", content="Odpowiedź")])
    state  = State(input_text="x")

    first  = await agent.run(state)
    second = await agent.run(state)

    assert first["messages"][0].tool_calls[0].name == "find_tickets_vector"
    assert second["messages"][0].content          == "Odpowiedź"

    with pytest.raises(LLMError):
        await agent.run(state)


async def test_run_tools_answers_every_call_by_its_id() -> None:
    """Tura z wywołaniem narzędzia → jedna wiadomość `tool` z tym samym `call_id` i źródła, jeśli
    je podano."""
    ref   = SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")
    state = State(input_text="x", messages=[SEARCH])

    node  = FakeRunToolsNode(result_text='{"cards": []}', sources=[ref])

    update = await node.run(state)

    assert [message.call_id for message in update["messages"]] == ["call_1"]
    assert update["messages"][0].content == '{"cards": []}'
    assert update["sources"]             == [ref]


async def test_run_tools_answers_each_tool_with_its_own_answer() -> None:
    """Odpowiedzi na konkretne narzędzia → wyszukiwanie dostaje sam tekst, odczyt tekst i źródła:
    tak atrapa odtwarza przebieg, w którym źródła dokłada dopiero odczyt."""
    ref  = SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")
    read = tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]}, call_id="call_2")
    node = FakeRunToolsNode(
        answers = {
            "find_tickets_vector": FakeToolAnswer(text='{"tickets": []}'),
            "read_tickets_card":   FakeToolAnswer(text='{"cards": []}', sources=[ref]),
        },
    )

    searched = await node.run(State(input_text="x", messages=[SEARCH]))
    answered = await node.run(State(input_text="x", messages=[SEARCH, read]))

    assert searched["messages"][0].content == '{"tickets": []}'
    assert "sources" not in searched
    assert answered["messages"][0].content == '{"cards": []}'
    assert answered["sources"]             == [ref]
    assert answered["log"][0].message      == "wywołania: read_tickets_card; źródła: 1"


async def test_run_tools_refuses_a_call_over_the_limit() -> None:
    """Drugie wywołanie narzędzia przy limicie 1 → błąd zamiast odpowiedzi i żadnych źródeł:
    atrapa egzekwuje limit tą samą regułą co węzeł właściwy, a model dostaje to jako wynik
    narzędzia, nie jako wywalone żądanie."""
    ref    = SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")
    first  = ChatMessage(role="tool", call_id="call_1", content="{}")
    second = tool_call_turn("find_tickets_vector", {"problem": "x", "symptoms": "y"}, "call_2")
    node   = FakeRunToolsNode(sources=[ref], limits={"find_tickets_vector": 1})

    allowed = await node.run(State(input_text="x", messages=[SEARCH]))
    refused = await node.run(State(input_text="x", messages=[SEARCH, first, second]))

    assert allowed["sources"] == [ref]
    assert json.loads(refused["messages"][0].content).keys() == {"error"}
    assert refused["messages"][0].call_id == "call_2"
    assert "sources" not in refused
    assert refused["log"][0].message.endswith("ponad limit: 1")


async def test_run_tools_without_sources_leaves_the_field_alone() -> None:
    """Atrapa bez źródeł → aktualizacja bez `sources`: graf bez narzędzi wiedzy nie ma tego pola."""
    update = await FakeRunToolsNode().run(State(input_text="x", messages=[SEARCH]))

    assert "sources" not in update


async def test_respond_sets_the_given_output() -> None:
    """Atrapa `respond` → `output` równy wynikowi z konstruktora, a stan zapisany w `calls`."""
    respond = FakeRespondNode(Verdict(verdict="pass"))

    update = await respond.run(State(input_text="x"))

    assert update["output"] == Verdict(verdict="pass")
    assert len(respond.calls) == 1


@pytest.mark.parametrize(
    "node",
    [FakeAgentNode(), FakeRunToolsNode(), FakeRespondNode(Verdict(verdict="pass"))],
    ids=lambda node: node.name,
)
async def test_every_fake_node_logs_one_entry_under_its_name(node: Node) -> None:
    """Wywołanie atrapy węzła → dokładnie jeden wpis w `log`, podpisany nazwą węzła."""
    update = await node.run(State(input_text="x", messages=[SEARCH]))

    assert [entry.node for entry in update["log"]] == [node.name]


async def test_the_agent_logs_which_tools_it_called() -> None:
    """Tura z wywołaniem narzędzia → wpis w logu nazywa narzędzie, nie cytuje argumentów."""
    update = await FakeAgentNode([SEARCH]).run(State(input_text="x"))

    assert update["log"][0].message == "tura 1: narzędzia: find_tickets_vector"
