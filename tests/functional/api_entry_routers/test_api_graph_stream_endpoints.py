import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.engine_anonymization import AnonymizationConfigError
from app.entry_routers.streaming import STREAM_MEDIA_TYPE
from app.errors import REQUEST_ID_HEADER
from app.main import create_app
from tests._helpers.anonymization import FAKE_ENGINE, anonymizer_client_on, service_answer
from tests._helpers.routers import (
    app_on_fake_graphs,
    app_with_model_failing_after_tools,
    sse_events,
)
from tests._helpers.routers.samples import GRAPH_REQUESTS, TICKET
from tests._helpers.transport import always, raising

# Strumień przebiegu z tras grafów (`Accept: text/event-stream`) w procesie, na atrapach grafów:
# kolejność zdarzeń, zgodność `result` z odpowiedzią JSON tej samej trasy, awarie i opis w OpenAPI.

# Nagłówek, którym wołający prosi o strumień.
STREAM = {"Accept": STREAM_MEDIA_TYPE}

# Każda trasa grafu z żądaniem do niej.
ROUTES = [pytest.param(path, body, id=path) for path, body in GRAPH_REQUESTS.items()]


@pytest.mark.parametrize("path, body", ROUTES)
def test_the_stream_ends_with_the_json_answer(
    path: str,             # wstrzykiwane przez pytest z listy ROUTES wyżej
    body: dict[str, Any],  # wstrzykiwane przez pytest z listy ROUTES wyżej
) -> None:
    """Sprawdza, czy trasa grafu poproszona o strumień odpowiada typem `text/event-stream`, a w nim
    same zdarzenia `step` i na końcu jedno `result` z dokładnie tą treścią, którą ta sama trasa
    oddaje JSON-em bez nagłówka.

    Wyłapuje strumień, który kończy się inną odpowiedzią niż JSON, gubi `result` albo wysyła
    zdarzenia po nim: front pokazałby inny wynik, niż dostałby helpdesk z tej samej sprawy."""
    client = TestClient(create_app())

    streamed = client.post(path, json=body, headers=STREAM)
    answered = client.post(path, json=body)
    events   = sse_events(streamed.text)

    assert streamed.headers["content-type"].startswith(STREAM_MEDIA_TYPE)
    assert [name for name, _ in events] == ["step"] * (len(events) - 1) + ["result"]
    assert events[-1][1] == answered.json()


@pytest.mark.parametrize("path, body", ROUTES)
def test_the_steps_follow_the_log_of_the_run(
    path: str,             # wstrzykiwane przez pytest z listy ROUTES wyżej
    body: dict[str, Any],  # wstrzykiwane przez pytest z listy ROUTES wyżej
) -> None:
    """Sprawdza, czy kroki strumienia idą tymi samymi węzłami i z tymi samymi opisami, co log
    przebiegu w odpowiedzi, po jednym kroku na wpis.

    Wyłapuje strumień, który pomija krok albo opisuje go inaczej niż log: konsola przebiegu
    pokazałaby inny przebieg, niż zapisał graf."""
    events = sse_events(TestClient(create_app()).post(path, json=body, headers=STREAM).text)

    steps = [data for name, data in events if name == "step"]
    log   = events[-1][1]["log"]

    assert [(step["node"], step["message"]) for step in steps] == [
        (entry["node"], entry["message"]) for entry in log
    ]


@pytest.mark.parametrize("path, body", ROUTES)
def test_a_dependency_failure_ends_the_stream_with_an_error_event(
    path: str,             # wstrzykiwane przez pytest z listy ROUTES wyżej
    body: dict[str, Any],  # wstrzykiwane przez pytest z listy ROUTES wyżej
) -> None:
    """Sprawdza, czy awaria usługi `anonymizer` przy strumieniu daje status 200 i jedno zdarzenie
    `error` w kształcie wspólnego błędu: opis „Anonymization failed" i identyfikator żądania ten
    sam, co w nagłówku odpowiedzi; zdarzenia `result` nie ma.

    Wyłapuje awarię, która zrywa strumień bez słowa albo kończy go odpowiedzią: front nie
    odróżniłby „usługa chwilowo nie działa" od urwanego połączenia albo pokazałby wynik, którego
    nie ma."""
    anonymizer = anonymizer_client_on(raising(httpx.ConnectError("connection refused")))
    client     = TestClient(app_on_fake_graphs(anonymizer))

    response = client.post(path, json=body, headers=STREAM)
    expected = {
        "detail":     "Anonymization failed",
        "request_id": response.headers[REQUEST_ID_HEADER],
    }

    assert response.status_code      == 200
    assert sse_events(response.text) == [("error", expected)]


def test_a_failure_in_the_middle_comes_after_the_steps_so_far() -> None:
    """Sprawdza, czy awaria modelu w drugiej turze `/search` przychodzi jako zdarzenie `error`
    z opisem awarii modelu, po krokach, które zdążyły się wykonać: anonimizacji, pierwszej
    turze i kroku narzędzi.

    Wyłapuje strumień, który przy awarii w środku gubi kroki wysłane wcześniej albo nie kończy
    się błędem: konsola przebiegu nie pokazałaby, na którym kroku sprawa stanęła."""
    client = TestClient(app_with_model_failing_after_tools())

    events = sse_events(client.post("/search", json=TICKET, headers=STREAM).text)

    assert [data.get("node", name) for name, data in events] == [
        "anonymize", "agent", "run_tools", "error",
    ]
    assert events[-1][1]["detail"] == "Language model call failed"


def test_a_config_error_breaks_the_stream() -> None:
    """Sprawdza, czy błąd konfiguracji w trakcie strumienia — anonimizator, który przy
    prawdziwym modelu odmawia wyniku atrapy silnika — zrywa strumień wyjątkiem, zamiast oddać
    zdarzenie `error`. Starlette podaje go jako `RuntimeError`, bo rodzina błędu ma handler,
    a odpowiedź już ruszyła; błąd konfiguracji jest jego przyczyną.

    Wyłapuje błąd konfiguracji przebrany za chwilową awarię: wołający czekałby i ponawiał, choć
    bez poprawki konfiguracji nic się nie zmieni."""
    anonymizer = anonymizer_client_on(always(payload=service_answer(engine=FAKE_ENGINE)))
    client     = TestClient(app_on_fake_graphs(anonymizer))

    with pytest.raises(RuntimeError) as broken:
        client.post("/search", json=TICKET, headers=STREAM)

    assert isinstance(broken.value.__cause__, AnonymizationConfigError)


def test_an_unknown_variant_is_refused_before_the_stream() -> None:
    """Sprawdza, czy `/suggest` z nieznanym wariantem odpowiada statusem 422 w JSON-ie także
    wtedy, gdy wołający prosi o strumień.

    Wyłapuje odmowę wysłaną jako zdarzenie strumienia ze statusem 200: literówka w nazwie guzika
    wyglądałaby jak udany przebieg."""
    request  = {**TICKET, "variant": "nie-ma-takiego"}
    response = TestClient(create_app()).post("/suggest", json=request, headers=STREAM)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


def test_the_steps_carry_no_ticket_text() -> None:
    """Sprawdza, czy żadne zdarzenie `step` strumienia `/search` nie zawiera opisu zgłoszenia
    z żądania.

    Wyłapuje krok, który niesie wejście grafu albo turę użytkownika: strumień trafia do
    przeglądarki, a ma nieść to samo co log przebiegu, czyli bez treści zgłoszenia."""
    events = sse_events(TestClient(create_app()).post("/search", json=TICKET, headers=STREAM).text)

    steps = [json.dumps(data, ensure_ascii=False) for name, data in events if name == "step"]

    assert steps
    assert all(TICKET["body"] not in step for step in steps)


def test_every_graph_route_has_the_stream_in_openapi() -> None:
    """Sprawdza, czy opis OpenAPI podaje przy odpowiedzi 200 każdej trasy grafu obie postacie,
    JSON i `text/event-stream`, i czy tras ze strumieniem jest dokładnie tyle, ile żądań
    w próbkach testu.

    Wyłapuje trasę grafu bez strumienia albo strumień niewidoczny w opisie API: front albo nowa
    trasa wypadłyby z tego testu bez czerwonego wyniku."""
    paths = TestClient(create_app()).get("/openapi.json").json()["paths"]

    streamed = {
        path for path, methods in paths.items()
        for operation in methods.values()
        if STREAM_MEDIA_TYPE in operation["responses"].get("200", {}).get("content", {})
    }

    assert streamed == set(GRAPH_REQUESTS)
    assert all(
        "application/json" in paths[path]["post"]["responses"]["200"]["content"]
        for path in streamed
    )
