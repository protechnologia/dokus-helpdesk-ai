import pytest

from app.agent_graphs.gate_close import (
    RESPOND_TOOL_NAME,
    GateCloseState,
    build_fake_graph,
    build_graph,
)
from app.agent_nodes.agent import FakeAgentNode
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.core_model.graphs.verdict import Verdict
from app.engine_anonymization import AnonymizedText, FakeAnonymizer
from app.engine_llm import LLMError

TICKET = "Nie przychodzą przesyłki z e-Doręczeń. Zrestartowano usługę odbioru."

BLOCK = Verdict(
    verdict = "block",
    reasons = ["Nie widać, co było przyczyną."],
    missing = ["przyczyna"],
    hint    = "Dopisz, dlaczego usługa stanęła.",
)

EXPECTED_EDGES = {
    ("__start__", "anonymize"),
    ("anonymize", "agent"),
    ("agent", "respond"),
    ("respond", "__end__"),
}


def make_state() -> GateCloseState:
    """
    Description:
    Buduje stan wejściowy bramki: jedno zgłoszenie i jedna reguła.

    Example args:
        (brak)

    Example result:
        GateCloseState(input_text="Nie przychodzą przesyłki…", rules=["Opis musi…"])
    """
    return GateCloseState(input_text=TICKET, rules=["Opis musi wskazywać problem."])


def test_the_graph_runs_anonymize_agent_respond_without_tools() -> None:
    """Sprawdza, czy graf bramki zamknięcia ma dokładnie trzy kroki w stałej kolejności:
    anonimizacja, jedna tura modelu i odpowiedź, bez kroku wykonującego narzędzia (`run_tools`).

    Wyłapuje graf złożony inaczej: z krokami w innej kolejności albo z narzędziami, przez które
    bramka sięgałaby do bazy wiedzy, choć ma działać także wtedy, gdy baza jest pusta."""
    graph = build_fake_graph().get_graph()

    assert {(edge.source, edge.target) for edge in graph.edges} == EXPECTED_EDGES
    assert "run_tools" not in graph.nodes


async def test_the_fake_graph_returns_the_given_verdict() -> None:
    """Sprawdza, czy atrapa grafu bramki oddaje dokładnie ten werdykt, który jej podano (tu
    blokujący, z powodem, brakiem i wskazówką), i czy model wydał go wywołaniem narzędzia
    odpowiedzi `respond_gate_close`, z tym samym werdyktem w argumentach.

    Wyłapuje atrapę, która gubi albo podmienia podany werdykt lub odpowiada zwykłym tekstem
    zamiast wywołania narzędzia: na tej atrapie stoją testy tras, więc sprawdzałyby co innego,
    niż zakładają."""
    state = GateCloseState(**await build_fake_graph(BLOCK).ainvoke(make_state()))
    call  = state.messages[-1].tool_calls[0]

    assert state.output                           == BLOCK
    assert call.name                              == RESPOND_TOOL_NAME
    assert Verdict.model_validate(call.arguments) == BLOCK


async def test_the_agent_runs_only_after_anonymization() -> None:
    """Sprawdza, czy anonimizator dostaje treść zgłoszenia, a węzeł modelu jest wołany dopiero ze
    stanem, w którym wersja po anonimizacji jest już zapisana.

    Wyłapuje graf, w którym model ruszyłby przed anonimizacją albo obok niej: surowe zgłoszenie
    z danymi klienta mogłoby wtedy wyjść do zewnętrznego modelu."""
    anonymizer = FakeAnonymizer()
    agent      = FakeAgentNode()
    graph      = build_graph(AnonymizeNode(anonymizer), agent, FakeRespondNode(BLOCK))

    await graph.ainvoke(make_state())

    assert anonymizer.texts          == [TICKET]
    assert agent.calls[0].anonymized == AnonymizedText(text=TICKET)


async def test_every_node_leaves_its_entry_in_the_log() -> None:
    """Sprawdza, czy po przebiegu grafu bramki dziennik przebiegu (`log`) ma po jednym wpisie od
    każdego węzła, w kolejności wywołań: anonimizacja, model, odpowiedź.

    Wyłapuje stan grafu, w którym nowy wpis nadpisuje poprzednie, zamiast się do nich dokleić:
    z całego przebiegu zostałby wtedy tylko ostatni krok i nie dałoby się odtworzyć, co się
    działo."""
    state = GateCloseState(**await build_fake_graph().ainvoke(make_state()))

    assert [entry.node for entry in state.log] == ["anonymize", "agent", "respond"]


def test_swapped_nodes_build_the_same_graph() -> None:
    """Sprawdza, czy węzły podane pod niewłaściwymi argumentami (odpowiedź w miejscu anonimizacji,
    anonimizacja w miejscu modelu, model w miejscu odpowiedzi) dają ten sam graf: o kolejności
    kroków decydują nazwy węzłów, nie miejsce w wywołaniu.

    Wyłapuje składanie grafu po pozycji argumentów: pomyłka w wywołaniu przestawiłaby wtedy
    kroki i model mógłby ruszyć przed anonimizacją."""
    graph = build_graph(
        anonymize = FakeRespondNode(BLOCK),
        agent     = AnonymizeNode(FakeAnonymizer()),
        respond   = FakeAgentNode(),
    )

    assert {(edge.source, edge.target) for edge in graph.get_graph().edges} == EXPECTED_EDGES


def test_two_nodes_with_one_name_fail_at_build() -> None:
    """Sprawdza, czy graf, któremu zamiast węzła odpowiedzi podano drugi węzeł modelu, w ogóle się
    nie złoży: dwa węzły o tej samej nazwie kończą budowę błędem `ValueError`.

    Wyłapuje graf, który powstałby bez węzła odpowiedzi i dopiero w trakcie żądania okazałby się
    niezdolny do wydania werdyktu."""
    with pytest.raises(ValueError):
        build_graph(AnonymizeNode(FakeAnonymizer()), FakeAgentNode(), FakeAgentNode())


async def test_the_fake_graph_is_single_use() -> None:
    """Sprawdza, czy ta sama atrapa grafu uruchomiona drugi raz kończy się błędem `LLMError`:
    atrapa modelu ma zaplanowaną jedną turę i po jej oddaniu nie ma już czego odpowiedzieć.

    Wyłapuje atrapę, która przy ponownym użyciu po cichu powtarzałaby starą odpowiedź: kod
    budujący graf raz na proces zamiast na każde żądanie przeszedłby wtedy niezauważony."""
    graph = build_fake_graph()

    await graph.ainvoke(make_state())

    with pytest.raises(LLMError):
        await graph.ainvoke(make_state())
