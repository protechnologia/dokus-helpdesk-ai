import json

import pytest
from starlette.requests import Request

from app.entry_routers.models import LogItem
from app.entry_routers.streaming import get_graph_responder, sse_event
from tests._helpers.routers import sse_events

# Nagłówek `Accept` i czy trasa ma odpowiedzieć strumieniem.
ACCEPT = [
    pytest.param(None, False, id="brak nagłówka"),
    pytest.param("application/json", False, id="JSON"),
    pytest.param("*/*", False, id="cokolwiek"),
    pytest.param("text/event-stream", True, id="strumień"),
    pytest.param("application/json, text/event-stream", True, id="strumień obok JSON-a"),
]


def test_an_event_is_one_event_line_and_one_data_line() -> None:
    """Sprawdza, czy zdarzenie SSE to linia z nazwą, jedna linia danych z JSON-em modelu i pusta
    linia na końcu, także gdy tekst w modelu ma znaki nowej linii.

    Wyłapuje JSON wypisany w kilku liniach: przeglądarka wzięłaby wtedy każdą linię za osobne pole
    albo skleiła dane źle, a front nie odczytałby kroku."""
    item = LogItem(node="agent", message="pierwsza linia\ndruga linia")

    event = sse_event("step", item)

    assert event.endswith("\n\n")
    assert event.count("\n") == 3
    assert sse_events(event) == [("step", json.loads(item.model_dump_json()))]


@pytest.mark.parametrize("accept, stream", ACCEPT)
def test_the_stream_is_chosen_by_the_accept_header(
    accept: str | None,  # wstrzykiwane przez pytest z listy ACCEPT wyżej
    stream: bool,        # wstrzykiwane przez pytest z listy ACCEPT wyżej
) -> None:
    """Sprawdza, czy trasa odpowiada strumieniem wtedy i tylko wtedy, gdy nagłówek `Accept`
    wymienia `text/event-stream`, także obok innych typów; bez nagłówka, przy JSON-ie
    i przy „cokolwiek" odpowiada JSON-em.

    Wyłapuje strumień wysłany wołającemu, który go nie prosił, albo pominięty przy nagłówku
    z kilkoma typami: helpdesk dostałby zdarzenia zamiast JSON-a, a front — JSON zamiast
    kroków."""
    request = Request({"type": "http", "method": "POST", "path": "/search", "headers": []})

    responder = get_graph_responder(request, accept)

    assert responder.stream is stream
