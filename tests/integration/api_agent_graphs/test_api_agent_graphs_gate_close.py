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
from app.anonymization import AnonymizedText, FakeAnonymizer
from app.llm import LLMError
from app.model.gate_verdict import Verdict

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
    """Graf bramki → anonymize, agent, respond po kolei, bez `run_tools`: bramka nie ma narzędzi."""
    graph = build_fake_graph().get_graph()

    assert {(edge.source, edge.target) for edge in graph.edges} == EXPECTED_EDGES
    assert "run_tools" not in graph.nodes


async def test_the_fake_graph_returns_the_given_verdict() -> None:
    """Atrapa grafu z werdyktem `block` → `output` to ten werdykt, a agent wydał go wywołaniem
    `respond_gate_close`."""
    state = GateCloseState(**await build_fake_graph(BLOCK).ainvoke(make_state()))
    call  = state.messages[-1].tool_calls[0]

    assert state.output                           == BLOCK
    assert call.name                              == RESPOND_TOOL_NAME
    assert Verdict.model_validate(call.arguments) == BLOCK


async def test_the_agent_runs_only_after_anonymization() -> None:
    """Przebieg → anonimizator dostaje `input_text`, a agent stan z już ustawionym `anonymized`."""
    anonymizer = FakeAnonymizer()
    agent      = FakeAgentNode()
    graph      = build_graph(AnonymizeNode(anonymizer), agent, FakeRespondNode(BLOCK))

    await graph.ainvoke(make_state())

    assert anonymizer.texts          == [TICKET]
    assert agent.calls[0].anonymized == AnonymizedText(text=TICKET)


async def test_every_node_leaves_its_entry_in_the_log() -> None:
    """Przebieg → w `log` po wpisie od każdego węzła, w kolejności: reduktor z `GraphState`
    dokleja wpisy, a nie nadpisuje ich ostatnim."""
    state = GateCloseState(**await build_fake_graph().ainvoke(make_state()))

    assert [entry.node for entry in state.log] == ["anonymize", "agent", "respond"]


def test_swapped_nodes_build_the_same_graph() -> None:
    """Węzły w zamienionych argumentach → ten sam przebieg: krawędzie idą po nazwach węzłów."""
    graph = build_graph(
        anonymize = FakeRespondNode(BLOCK),
        agent     = AnonymizeNode(FakeAnonymizer()),
        respond   = FakeAgentNode(),
    )

    assert {(edge.source, edge.target) for edge in graph.get_graph().edges} == EXPECTED_EDGES


def test_two_nodes_with_one_name_fail_at_build() -> None:
    """Dwa agenty zamiast agenta i `respond` → błąd przy składaniu, a nie graf bez werdyktu."""
    with pytest.raises(ValueError):
        build_graph(AnonymizeNode(FakeAnonymizer()), FakeAgentNode(), FakeAgentNode())


async def test_the_fake_graph_is_single_use() -> None:
    """Drugie wywołanie tej samej atrapy grafu → błąd: `FakeAgentNode` ma jedną turę, więc atrapę
    buduje się na każde wywołanie."""
    graph = build_fake_graph()

    await graph.ainvoke(make_state())

    with pytest.raises(LLMError):
        await graph.ainvoke(make_state())
