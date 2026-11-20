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
from app.core_service.factory_mail_normalizer import get_mail_normalizer
from app.core_service.normalizer_ticket_mail import MailNormalizer
from app.engine_anonymization import Anonymizer, FakeAnonymizer
from app.main import create_app
from tests._helpers.routers.samples import GRAPH_REQUESTS


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
    anonymizer: Anonymizer,                   # np. FakeAnonymizer() — zapisuje teksty w `texts`
    mail:       MailNormalizer | None = None,  # np. MailNormalizer(SAFE_MAIL_DIR)
) -> FastAPI:
    """
    Description:
    Aplikacja, w której każda trasa grafu dostaje atrapę swojego grafu na podanym anonimizatorze
    — do odtworzenia awarii anonimizacji, która jest pierwszym krokiem każdego grafu, i do
    podejrzenia tekstu, który do niej trafia. Podany normalizer maili zastępuje ten
    z konfiguracji; bez niego trasy czytają słownik maili z `TICKETS_MAIL_DIR`.

    Example args:
        anonymizer=FakeAnonymizer()
        mail=MailNormalizer(SAFE_MAIL_DIR)

    Example result:
        FastAPI, której trasy grafów anonimizują podanym anonimizatorem
    """
    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda module: module.build_fake_graph(anonymizer)
    )

    if mail is not None:
        app.dependency_overrides[get_mail_normalizer] = lambda: mail

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


def ticket_request(
    route:  str,             # np. "/suggest"
    ticket: dict[str, Any],  # np. {"ticket_id": "41101", "body": "Dzień dobry,…", …}
) -> dict[str, Any]:
    """
    Description:
    Dokłada do podanego zgłoszenia pola, których poza zgłoszeniem wymaga trasa grafu — dziś
    wariant przy `/suggest` — biorąc je z żądania tej trasy w `GRAPH_REQUESTS`.

    Example args:
        route="/suggest"
        ticket={"ticket_id": "41101", "body": "Dzień dobry,…", …}

    Example result:
        {"ticket_id": "41101", "body": "Dzień dobry,…", …, "variant": "questions"}
    """
    extra   = {key: value for key, value in GRAPH_REQUESTS[route].items() if key == "variant"}
    request = {**ticket, **extra}

    return request
