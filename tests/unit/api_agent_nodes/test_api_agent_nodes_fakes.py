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
from app.engine_llm import ChatMessage, LLMError, LLMUsage


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
    """Sprawdza, czy atrapa węzła `agent` bez zaplanowanych tur oddaje jedną turę modelu z samą
    odpowiedzią, bez wywołań narzędzi, i podbija licznik tur do 1.

    Wyłapuje atrapę, która domyślnie woła narzędzia albo nie liczy tur: testy grafów, które na niej
    stoją, przestałyby odtwarzać najprostszy przebieg, czyli jedną turę i odpowiedź."""
    update = await FakeAgentNode().run(State(input_text="x"))

    assert update["iterations"]            == 1
    assert update["messages"][0].role      == "assistant"
    assert update["messages"][0].tool_calls == []


async def test_the_agent_plays_its_turns_in_order() -> None:
    """Sprawdza, czy atrapa węzła `agent` oddaje zaplanowane tury po kolei (tu najpierw wywołanie
    wyszukiwania, potem odpowiedź), a trzecie wywołanie kończy błędem zamiast powtórki.

    Wyłapuje atrapę, która myli kolejność tur albo po ich wyczerpaniu odpowiada dalej: test grafu
    nie zauważyłby wtedy, że graf pyta model częściej, niż zakładano."""
    agent  = FakeAgentNode([SEARCH, ChatMessage(role="assistant", content="Odpowiedź")])
    state  = State(input_text="x")

    first  = await agent.run(state)
    second = await agent.run(state)

    assert first["messages"][0].tool_calls[0].name == "find_tickets_vector"
    assert second["messages"][0].content          == "Odpowiedź"

    with pytest.raises(LLMError):
        await agent.run(state)


async def test_run_tools_answers_every_call_by_its_id() -> None:
    """Sprawdza, czy atrapa węzła `run_tools` odpowiada na wywołanie narzędzia jedną wiadomością
    z wynikiem, oznaczoną identyfikatorem tego wywołania, i dokłada źródła podane przy budowie.

    Wyłapuje atrapę, która gubi identyfikator wywołania albo podane źródła: wyniku nie dałoby się
    przypisać do wywołania, a testy grafów nie miałyby listy źródeł do sprawdzenia."""
    ref   = SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")
    state = State(input_text="x", messages=[SEARCH])

    node  = FakeRunToolsNode(result_text='{"cards": []}', sources=[ref])

    update = await node.run(state)

    assert [message.call_id for message in update["messages"]] == ["call_1"]
    assert update["messages"][0].content == '{"cards": []}'
    assert update["sources"]             == [ref]


async def test_run_tools_answers_each_tool_with_its_own_answer() -> None:
    """Sprawdza, czy atrapa węzła `run_tools` z osobnymi odpowiedziami na narzędzia oddaje każdemu
    swoją: wyszukiwanie dostaje sam tekst, bez źródeł, a odczyt kart tekst i jedno źródło,
    odnotowane w dzienniku przebiegu.

    Wyłapuje atrapę, która miesza odpowiedzi albo dokłada źródła już przy wyszukiwaniu: nie dałoby
    się na niej odtworzyć przebiegu, w którym źródła pojawiają się dopiero po odczycie."""
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
    """Sprawdza, czy przy limicie jednego wywołania atrapa węzła `run_tools` odpowiada na drugie
    wyszukiwanie komunikatem o błędzie zamiast wyniku, nie dokłada przy nim źródeł i odnotowuje
    w dzienniku jedno wywołanie ponad limit. Pierwsze wyszukiwanie dokłada źródło jak zwykle.

    Wyłapuje atrapę, która limitu nie egzekwuje albo przerywa przebieg: ma stosować tę samą regułę
    co węzeł właściwy, a model ma dostać odmowę jako wynik narzędzia, nie jako błąd żądania."""
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
    """Sprawdza, czy atrapa węzła `run_tools` zbudowana bez źródeł w ogóle nie zwraca pola
    `sources`.

    Wyłapuje atrapę, która zawsze oddaje to pole, choćby puste: stan grafu bez narzędzi wiedzy go
    nie ma, więc taka zmiana stanu nie pasowałaby do grafu."""
    update = await FakeRunToolsNode().run(State(input_text="x", messages=[SEARCH]))

    assert "sources" not in update


async def test_respond_sets_the_given_output() -> None:
    """Sprawdza, czy atrapa węzła `respond` ustawia jako wynik grafu dokładnie to, co dostała przy
    budowie, i zapamiętuje stan, z którym ją wywołano.

    Wyłapuje atrapę, która podmienia wynik albo nie zapisuje wywołań: testy grafów nie mogłyby wtedy
    sprawdzić ani wyniku, ani tego, z jakim stanem przebieg doszedł do odpowiedzi."""
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
    """Sprawdza, czy każda atrapa węzła (`agent`, `run_tools`, `respond`) dopisuje przy wywołaniu
    dokładnie jeden wpis do dziennika przebiegu, podpisany własną nazwą.

    Wyłapuje atrapę, która nie zostawia wpisu albo podpisuje go cudzą nazwą: testy grafów odczytują
    kolejność węzłów właśnie z dziennika, więc widziałyby inny przebieg niż rzeczywisty."""
    update = await node.run(State(input_text="x", messages=[SEARCH]))

    assert [entry.node for entry in update["log"]] == [node.name]


async def test_the_agent_logs_which_tools_it_called() -> None:
    """Sprawdza, czy po turze z wywołaniem narzędzia atrapa węzła `agent` zapisuje w dzienniku
    przebiegu numer tury, nazwę narzędzia i koszt tury („tura 1: narzędzia: find_tickets_vector;
    0,0000 USD"), bez argumentów.

    Wyłapuje wpis, który cytuje argumenty wywołania: to dane klienta, a dziennik wraca do wołającego
    razem z odpowiedzią."""
    update = await FakeAgentNode([SEARCH]).run(State(input_text="x"))

    assert update["log"][0].message == "tura 1: narzędzia: find_tickets_vector; 0,0000 USD"


def test_the_log_entry_of_a_turn_carries_its_cost() -> None:
    """Sprawdza, czy wpis w dzienniku po turze, która kosztowała 0,03214 USD, kończy się kosztem
    zaokrąglonym do czterech miejsc i zapisanym z przecinkiem („0,0321 USD"), a zużycie tej tury
    wraca w zmianie stanu bez zmian, jako liczba.

    Wyłapuje wpis bez kosztu albo z kosztem całej sprawy zamiast tury: czytający przebieg nie
    widziałby, która tura była droga. Wyłapuje też zapis, w którym liczba trafia do logu, a ginie
    z pola `usage`, po którym graf sumuje koszt sprawy."""
    usage = LLMUsage(calls=1, prompt_tokens=4820, cost_usd=0.03214)

    update = FakeAgentNode([SEARCH]).turn_update(State(input_text="x"), [SEARCH], usage)

    assert update["log"][0].message == "tura 1: narzędzia: find_tickets_vector; 0,0321 USD"
    assert update["usage"]          == usage
