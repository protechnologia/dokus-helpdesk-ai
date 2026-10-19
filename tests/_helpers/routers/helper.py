import json
from typing import Any

from fastapi import FastAPI

from app.agent_graphs import search
from app.agent_graphs.factory import get_graph_builder
from app.agent_graphs.fake import FAKE_MAX_ITERATIONS, FAKE_SEARCH_ARGUMENTS
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode
from app.engine_anonymization import Anonymizer, FakeAnonymizer
from app.main import create_app


def sse_events(
    text: str,  # np. 'event: step\ndata: {"node": "agent", …}\n\nevent: result\ndata: {…}\n\n'
) -> list[tuple[str, dict[str, Any]]]:
    """
    Description:
    Rozbiera treść strumienia SSE na zdarzenia: nazwę z linii `event` i JSON z linii `data`,
    w kolejności, w jakiej przyszły. Zdarzenie bez którejś z tych linii to błąd testu.

    Example args:
        text='event: step\ndata: {"node": "agent"}\n\nevent: result\ndata: {"verdict": "pass"}\n\n'

    Example result:
        [("step", {"node": "agent"}), ("result", {"verdict": "pass"})]
    """
    events = []

    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))

    return events


def app_on_fake_graphs(
    anonymizer: Anonymizer,  # np. anonymizer_client_on(raising(httpx.ConnectError("…")))
) -> FastAPI:
    """
    Description:
    Aplikacja, w której każda trasa grafu dostaje atrapę swojego grafu na podanym anonimizatorze
    — do odtworzenia awarii anonimizacji, która jest pierwszym krokiem każdego grafu.

    Example args:
        anonymizer=anonymizer_client_on(raising(httpx.ConnectError("connection refused")))

    Example result:
        FastAPI, której trasy grafów anonimizują podanym anonimizatorem
    """
    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda module: module.build_fake_graph(anonymizer)
    )

    return app


def app_with_model_failing_after_tools() -> FastAPI:
    """
    Description:
    Aplikacja, w której graf `search` przechodzi anonimizację, turę modelu z wyszukaniem i krok
    narzędzi, a przy drugiej turze model zawodzi (`LLMError`): atrapa agenta ma zaplanowaną
    jedną turę, a brak kolejnej to błąd. Tak wygląda awaria zależności w środku przebiegu.

    Example args:
        (brak)

    Example result:
        FastAPI, której `/search` po trzech krokach kończy się awarią modelu
    """
    only_search = tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS)

    graph = search.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = FakeAgentNode([only_search]),
        run_tools      = FakeRunToolsNode(),
        respond        = FakeRespondNode(search.SearchNotes(internal_notes="nieosiągalne")),
        max_iterations = FAKE_MAX_ITERATIONS,
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    return app
