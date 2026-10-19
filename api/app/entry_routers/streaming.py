"""
Description:
Odpowiedź tras grafów JSON-em albo strumieniem przebiegu, zależnie od nagłówka `Accept`. Ta sama
trasa obsługuje obie drogi, więc graf, budowa stanu i odpowiedź zostają w jednym miejscu.

| `Accept`                   | odpowiedź                                                   |
|----------------------------|-------------------------------------------------------------|
| brak albo inny             | JSON trasy, jak dotąd                                       |
| zawiera `text/event-stream`| strumień SSE: `step` po każdym kroku grafu, na końcu        |
|                            | `result` z tą samą treścią co JSON albo `error` przy awarii |

Przykład strumienia `POST /search` (zdarzenia skrócone):

    event: step
    data: {"node": "anonymize", "message": "zanonimizowano 72 zn.", "started_at": "…", …}

    event: step
    data: {"node": "agent", "message": "tura 1: narzędzia: find_tickets_vector; 0,0041 USD", …}

    event: step
    data: {"node": "run_tools", …, "tool_calls": [{"tool": "find_tickets_vector", …}]}

    event: result
    data: {"sources": […], "internal_notes": "## Zgłoszenia historyczne\\n…", …}

O czym pamiętać przy zmianach:

- Status strumienia to zawsze 200: nagłówki wychodzą przed pierwszym krokiem. Awarię zależności
  w trakcie przebiegu niesie zdarzenie `error` (`ErrorResponse`), opisane tą samą funkcją co
  503 w handlerze. Błąd konfiguracji zrywa strumień, jak dziś daje 500. W logu stoi wtedy
  `RuntimeError: Caught handled exception, but response already started`, bo rodzina błędu ma
  handler, a odpowiedź już ruszyła; błąd konfiguracji jest jego przyczyną, niżej w śladzie.
- Odpowiedź 422 (walidacja żądania, nieznany wariant) pada przed startem strumienia, więc
  zostaje zwykłą odpowiedzią HTTP.
- Middleware żądań loguje czas do wysłania nagłówków, nie do końca strumienia.
"""

from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import Header, Request
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.agent_graphs import run_graph, stream_graph
from app.entry_routers.mapping import to_step_item
from app.errors import DEPENDENCY_FAILURES, dependency_failure, request_id_of

# Typ odpowiedzi strumienia przebiegu: Server-Sent Events.
STREAM_MEDIA_TYPE = "text/event-stream"

# Bez cache i bez buforowania w pośredniku (nginx): inaczej kroki dotarłyby do przeglądarki
# wszystkie naraz, na końcu przebiegu.
STREAM_HEADERS = {
    "Cache-Control":     "no-cache",
    "X-Accel-Buffering": "no",
}

# Wariant strumienia w opisie OpenAPI, dokładany do każdej trasy grafu obok odpowiedzi JSON.
STREAM_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "JSON albo, przy `Accept: text/event-stream`, strumień zdarzeń `step` "
                       "(StepItem), a na końcu `result` (ta sama treść co JSON) albo `error` "
                       "(ErrorResponse).",
        "content":     {STREAM_MEDIA_TYPE: {"schema": {"type": "string"}}},
    },
}


def sse_event(
    name: str,        # np. "step"
    body: BaseModel,  # np. StepItem(node="agent", message="tura 1: …", …)
) -> str:
    """
    Description:
    Składa jedno zdarzenie SSE: nazwa w linii `event`, model jako JSON w jednej linii `data`
    i pusta linia, która zdarzenie kończy. JSON nie ma znaków nowej linii poza ucieczkami, więc
    jedna linia `data` wystarcza.

    Example args:
        name="step"
        body=LogItem(node="agent", message="tura 1")

    Example result:
        'event: step\\ndata: {"node":"agent","message":"tura 1"}\\n\\n'
    """
    return f"event: {name}\ndata: {body.model_dump_json()}\n\n"


class GraphResponder:
    """
    Description:
    Oddaje wynik grafu trasy tak, jak prosi wołający: odpowiedzią JSON albo strumieniem przebiegu.

    Do czego:
    Trasa grafu ma jedną drogę od żądania do stanu i jedną od stanu końcowego do odpowiedzi
    (`finish`: mapowanie i log), a ten obiekt decyduje tylko, jak je oddać. Dzięki temu zdarzenie
    `result` ma zawsze tę samą treść co JSON, a front pokazowy (p. 77) widzi kroki na żywo.

    Flow:
        1. Zależność `get_graph_responder()` czyta nagłówek `Accept`, ścieżkę i identyfikator
           żądania.
        2. Trasa składa stan i woła `answer()` z grafem i funkcją `finish`.
        3. Bez strumienia `answer()` przepuszcza stan przez graf i oddaje `finish(final)`.
        4. Ze strumieniem oddaje `StreamingResponse` na `_events()`: krok po kroku zdarzenia
           `step`, a na końcu `result` albo `error`.
    """

    def __init__(
        self,
        stream:     bool,        # np. True — wołający przysłał `Accept: text/event-stream`
        path:       str,         # np. "/search" — do logu awarii
        request_id: str | None,  # np. "8f14e45fceea167a5a36dedd4bea2543"
    ):
        """
        Description:
        Zapamiętuje, jak odpowiedzieć na to jedno żądanie.

        Example args:
            stream=True
            path="/search"
            request_id="8f14e45fceea167a5a36dedd4bea2543"

        Example result:
            GraphResponder, który odpowiada strumieniem
        """
        self.stream      = stream
        self._path       = path
        self._request_id = request_id

    async def answer(
        self,
        graph:  CompiledStateGraph,          # np. search.build_fake_graph(FakeAnonymizer())
        state:  BaseModel,                   # np. SearchState(input_text="ZGŁOSZENIE 41002…")
        finish: Callable[[Any], BaseModel],  # np. stan końcowy → SearchResponse, z logiem trasy
    ) -> BaseModel | StreamingResponse:
        """
        Description:
        Przepuszcza stan przez graf i oddaje odpowiedź trasy: model, który FastAPI zamieni na
        JSON, albo strumień przebiegu.

        Example args:
            graph=search.build_fake_graph(FakeAnonymizer())
            state=SearchState(input_text="ZGŁOSZENIE 41002\nOd wczoraj nie przychodzą…")
            finish=<funkcja trasy: to_search_response() i wpis w logu>

        Example result:
            SearchResponse(sources=[…], internal_notes="…", …) albo StreamingResponse(…)
        """
        # --- JSON: cały przebieg, potem odpowiedź ---
        if not self.stream:
            final = await run_graph(graph, state)

            return finish(final)

        # --- strumień: kroki w trakcie, odpowiedź na końcu ---
        events   = self._events(graph, state, finish)
        response = StreamingResponse(events, media_type=STREAM_MEDIA_TYPE, headers=STREAM_HEADERS)

        return response

    async def _events(
        self,
        graph:  CompiledStateGraph,          # np. search.build_fake_graph(FakeAnonymizer())
        state:  BaseModel,                   # np. SearchState(input_text="ZGŁOSZENIE 41002…")
        finish: Callable[[Any], BaseModel],  # np. stan końcowy → SearchResponse, z logiem trasy
    ) -> AsyncIterator[str]:
        """
        Description:
        Zdarzenia strumienia: `step` po każdym kroku grafu, a na końcu `result` z odpowiedzią
        trasy albo `error`, gdy w trakcie zawiodła zależność.

        Example args:
            graph=search.build_fake_graph(FakeAnonymizer())
            state=SearchState(input_text="ZGŁOSZENIE 41002\nOd wczoraj nie przychodzą…")
            finish=<funkcja trasy: to_search_response() i wpis w logu>

        Example result:
            'event: step\\ndata: {"node": "anonymize", …}\\n\\n', …,
            'event: result\\ndata: {"sources": […], …}\\n\\n'

        Raises:
            LLMConfigError, AnonymizationConfigError i pozostałe błędy konfiguracji zależności:
                zrywają strumień, bo czekanie ich nie naprawi
        """
        # Stan po ostatnim kroku to stan końcowy, ten sam, który dałby `run_graph()`.
        try:
            async for step, after in stream_graph(graph, state):
                yield sse_event("step", to_step_item(step))
                final = after
        except tuple(DEPENDENCY_FAILURES) as exc:  # awaria zależności: status już wyszedł
            yield sse_event("error", dependency_failure(exc, self._path, self._request_id))
            return

        yield sse_event("result", finish(final))


def get_graph_responder(
    request: Request,                    # wstrzykiwane przez FastAPI: żądanie HTTP
    accept:  str | None = Header(None),  # np. "text/event-stream"
) -> GraphResponder:
    """
    Description:
    Zależność FastAPI dla tras grafów: obiekt, który odpowie na to żądanie JSON-em albo
    strumieniem. Strumień, gdy nagłówek `Accept` wymienia `text/event-stream`, także obok innych
    typów.

    Example args:
        request=Request(scope={...})
        accept="text/event-stream"

    Example result:
        GraphResponder(stream=True, path="/search", request_id="8f14…")
    """
    responder = GraphResponder(
        stream     = accept is not None and STREAM_MEDIA_TYPE in accept,
        path       = request.url.path,
        request_id = request_id_of(request),
    )

    return responder
