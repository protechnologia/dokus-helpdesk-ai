"""
Description:
Transport doubles shared by the tests of every HTTP client we write (`EmbeddingClient`,
`QdrantClient`, and whatever crosses a process boundary next). They answer, record or fail in
place of a socket, so a client's contract is testable without the service behind it.

Why a plain module and not `conftest.py`: these are helpers called explicitly, not fixtures
injected by pytest. Putting them in `conftest.py` would make them look like magic and hide the
import that says where they come from. It sits at `tests/` level rather than under `unit/` so an
integration test can reach for the same doubles.

Four axes, one function each — the same split every client test needs (CLAUDE.md -> "Testy",
"ile w pliku jest osi, tyle helperów"):

    always()    — one canned answer to everything; the ANSWER is the subject
    routed()    — a different answer per (method, path); for clients whose calls are a
                  CONVERSATION (read before write, read before delete)
    capturing() — records every request; the REQUEST is the subject
    raising()   — does not answer at all; the transport is BROKEN

`always()` and `routed()` stay separate on purpose. Routing is the general case, but a client
speaking to a single endpoint would have to name that path in every test just to say "answer this"
— which reads as if the path mattered, when the test is about the body.
"""

import json

import httpx

# Fallback for a request no route matched. A permissive default rather than a 404, so a test
# declares only the calls it actually cares about; a test that cares about the miss asserts on
# what was captured instead.
DEFAULT_RESPONSE_BODY = {"result": {}, "status": "ok"}


def with_transport(
    client:  object,                 # e.g. EmbeddingClient(base_url="http://embedder:8000")
    handler: httpx.MockTransport,    # e.g. always({"vectors": [[0.1]]})
) -> object:
    """
    Description:
    Points an already-built client at a handler instead of a socket, and returns it.

    The private `_client` attribute is replaced deliberately: `httpx` offers no public seam for
    this, and adding a constructor argument that only tests would pass would put test scaffolding
    into production code. Written once here so the reasoning is not re-derived by every client
    test — the third one would otherwise copy the same comment a third time.

    Works on any client following our transport convention (an `httpx.AsyncClient` on `_client`),
    which is why it takes `object`: it is deliberately blind to WHICH client it is rigging.

    Example args:
        client=EmbeddingClient(base_url="http://embedder:8000")
        handler=always({"vectors": [[0.1, -0.2]]})

    Example result:
        The same client, answering from the handler
    """
    base_url = str(client._client.base_url)  # keep the URL the client was configured with

    client._client = httpx.AsyncClient(transport=handler, base_url=base_url)

    return client


def always(
    payload: dict | None = None,  # e.g. {"vectors": [[0.1, -0.2]]}
    status:  int         = 200,
    text:    str | None  = None,  # e.g. "<html>oops</html>" — wins over `payload` when given
) -> httpx.MockTransport:
    """
    Description:
    Builds a transport answering EVERY request the same way. For clients that speak to one
    endpoint, and for tests where the answer is the subject — counts, shapes, statuses.

    `text` exists for the case a JSON body cannot express: a 200 carrying a proxy's HTML error
    page, which is what a caller actually meets when something sits between us and the service.

    Example args:
        payload={"vectors": [[0.1, -0.2]]}
        status=200

    Example result:
        httpx.MockTransport returning 200 with that body
    """
    if text is not None:
        return httpx.MockTransport(lambda request: httpx.Response(status, text=text))

    body = payload if payload is not None else DEFAULT_RESPONSE_BODY

    return httpx.MockTransport(lambda request: httpx.Response(status, json=body))


def routed(
    routes: dict[tuple[str, str], httpx.Response],  # e.g. {("GET", "/x"): Response(404)}
) -> httpx.MockTransport:
    """
    Description:
    Builds a transport answering per (method, path). For clients whose operations are a
    conversation rather than a single call — Qdrant's `ensure_collection` reads before it writes,
    `delete_collection` reads before it deletes, and a single canned answer cannot express that.

    Unrouted requests get `DEFAULT_RESPONSE_BODY` with a 200, so each test names only the calls it
    reasons about.

    Example args:
        routes={("GET", "/collections/tickets"): httpx.Response(404)}

    Example result:
        httpx.MockTransport answering 404 for that read and 200 for everything else
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(
            (request.method, request.url.path),
            httpx.Response(200, json=DEFAULT_RESPONSE_BODY),
        )

    return httpx.MockTransport(handler)


def capturing(
    seen:   list,                                            # filled in place, one entry per call
    routes: dict[tuple[str, str], httpx.Response] | None = None,
) -> httpx.MockTransport:
    """
    Description:
    Builds a transport recording every request into `seen` and answering as `routed()` would. The
    counterpart of the two above: here the REQUEST is the subject — what actually went on the wire.

    Records a LIST rather than merging bodies into a dict, even for single-call clients: order and
    call count are part of what a test may need to prove ("it read before it wrote", "one batch or
    three"), and a merged dict destroys both. The price is one extra index at the assertion —
    `seen[0]["body"]` instead of `seen`.

    Example args:
        seen=[]
        routes={("GET", "/collections/tickets"): httpx.Response(404)}

    Example result:
        httpx.MockTransport filling `seen` with
        [{"method": "GET", "path": "/collections/tickets", "params": {}, "body": None}]
    """
    answers = routes or {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "method": request.method,
                "path":   request.url.path,
                "params": dict(request.url.params),
                # Bodyless requests (GET, DELETE) record None rather than failing to decode.
                "body":   json.loads(request.content) if request.content else None,
            }
        )

        return answers.get(
            (request.method, request.url.path),
            httpx.Response(200, json=DEFAULT_RESPONSE_BODY),
        )

    return httpx.MockTransport(handler)


def raising(
    error: Exception,  # e.g. httpx.ConnectError("connection refused")
) -> httpx.MockTransport:
    """
    Description:
    Builds a transport that fails the way a broken connection does, rather than answering. The
    axis the other three cannot cover: there is no response at all, which is what a client must
    translate into its own layer's error instead of letting an `httpx` type escape (rule 4).

    Example args:
        error=httpx.ConnectError("connection refused")

    Example result:
        httpx.MockTransport raising that error on every request
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return httpx.MockTransport(handler)
