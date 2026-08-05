import logging

import httpx

from app.embedding.errors import EmbeddingConfigError, EmbeddingError

logger = logging.getLogger(__name__)

# Path of the embedding endpoint on the `embedder` service. A constant rather than a setting: the
# route is part of the contract between two services we ship together, not something an operator
# tunes — `EMBEDDING_BASE_URL` already says WHERE the service is.
EMBED_PATH = "/embed"


class EmbeddingClient:
    """
    Description:
    How `api` turns text into vectors: an HTTP client for the `embedder` service. "Client" here
    means a process boundary is crossed (CLAUDE.md -> "Warstwy kodu") — what actually runs the
    model lives on the other side and is called `Encoder`, never a client.

    Flow:
        1. Built once from `Settings` (base URL, timeout) and reused; the underlying
           `httpx.AsyncClient` keeps connections alive across calls.
        2. Domain code calls `embed_query()`, `embed_passage()` or `embed_sts()` — never a
           generic `embed(mode=…)`.
        3. Each of those posts the batch to `/embed` with its mode and returns one vector per
           text, in the order submitted.

    Why three methods instead of one with a `mode` argument: the mode decides which vector space
    the result belongs to, and mixing spaces destroys retrieval silently (CLAUDE.md ->
    "Embeddingi"). A parameter can be forwarded from a variable three call sites away, so that
    nobody notices which mode is in flight; three named methods force the choice to be spelled at
    the call site. The prefix strings themselves live in the `embedder` service, because what a
    mode MEANS is a property of the model, not of this contract.
    """

    def __init__(
        self,
        base_url: str,          # e.g. "http://embedder:8000"
        timeout:  float = 30.0, # seconds
    ):
        """
        Description:
        Builds the client for one `embedder` instance. Refuses an empty base URL: `httpx` would
        accept it and later fail with a confusing relative-URL error, far from the cause.

        Example args:
            base_url="http://embedder:8000"
            timeout=30.0

        Example result:
            EmbeddingClient posting to http://embedder:8000/embed

        Raises:
            EmbeddingConfigError: `EMBEDDING_BASE_URL` is empty
        """
        # Guard, not politeness: compose substitutes an EMPTY STRING for an undefined `${VAR:-}`,
        # and a client built on "" fails at request time with an unreadable message.
        if not base_url.strip():
            raise EmbeddingConfigError("EMBEDDING_BASE_URL nie może być puste")

        self._client = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # trailing slash would double up with EMBED_PATH
            timeout  = timeout,
        )

    async def embed_query(
        self,
        texts: list[str],  # e.g. ["Nie działa wysyłka do ePUAP"]
    ) -> list[list[float]]:
        """
        Description:
        Embeds NEW tickets asked as questions against the index — the runtime side of retrieval.
        Its results may only be searched against `passage` vectors, never against `sts` ones.

        Example args:
            texts=["Nie działa wysyłka do ePUAP"]

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EmbeddingError: the embedder is unreachable, timed out or answered with an error
        """
        return await self._embed(texts, "query")

    async def embed_passage(
        self,
        texts: list[str],  # e.g. ["Brak tonera w drukarce sieciowej"]
    ) -> list[list[float]]:
        """
        Description:
        Embeds historical tickets being INDEXED — the documents a query is matched against.

        Example args:
            texts=["Brak tonera w drukarce sieciowej"]

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EmbeddingError: the embedder is unreachable, timed out or answered with an error
        """
        return await self._embed(texts, "passage")

    async def embed_sts(
        self,
        texts: list[str],  # e.g. ["Brak tonera w drukarce sieciowej"]
    ) -> list[list[float]]:
        """
        Description:
        Embeds text for SYMMETRIC ticket-to-ticket comparison: dedup at indexing time and
        "similar cases". Both sides of such a comparison must be embedded this way — the model
        was trained with the prefix on both, not on one.

        Example args:
            texts=["Brak tonera w drukarce sieciowej"]

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EmbeddingError: the embedder is unreachable, timed out or answered with an error
        """
        return await self._embed(texts, "sts")

    async def aclose(self) -> None:
        """
        Description:
        Releases the connection pool. Called when the application shuts down — an open pool keeps
        sockets alive and makes tests warn about unclosed transports.

        Example args:
            (none)

        Example result:
            None
        """
        await self._client.aclose()

    async def _embed(
        self,
        texts: list[str],  # e.g. ["Brak tonera"]
        mode:  str,        # e.g. "passage" — one of query/passage/sts
    ) -> list[list[float]]:
        """
        Description:
        Posts one batch in one mode and unwraps the response. The single place where transport
        failures become `EmbeddingError`, so no caller ever sees an `httpx` type.

        Example args:
            texts=["Brak tonera"]
            mode="passage"

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EmbeddingError: transport failed, the service answered non-2xx, or the payload was
                            not shaped as the contract promises
        """
        # Counts and mode only — the texts are ticket content, i.e. customer data, and belong to
        # DEBUG at most (CLAUDE.md -> "Logi i obserwowalność").
        logger.info("embed mode=%s batch_size=%d", mode, len(texts))

        # --- call ---
        try:
            response = await self._client.post(EMBED_PATH, json={"texts": texts, "mode": mode})
            response.raise_for_status()
        except httpx.TimeoutException as exc:          # the embedder did not answer in time
            raise EmbeddingError(f"Embedder timed out after {len(texts)} text(s)") from exc
        except httpx.HTTPStatusError as exc:           # answered, but with a non-2xx status
            raise EmbeddingError(
                f"Embedder returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:                 # connection refused, DNS, broken transport
            raise EmbeddingError(f"Could not reach the embedder: {exc}") from exc

        return self._extract_vectors(response, expected=len(texts))

    def _extract_vectors(
        self,
        response: httpx.Response,  # e.g. 200 with {"vectors": [[…]], "dimension": 768}
        expected: int,             # e.g. 1 — how many texts were submitted
    ) -> list[list[float]]:
        """
        Description:
        Reads the vectors out of a successful response and checks the count. Kept separate from
        the call so the shape rules are testable without a transport, and so `_embed` reads as
        "call, then unwrap".

        Example args:
            response=<Response [200 OK]>
            expected=1

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EmbeddingError: the body is not JSON, lacks `vectors`, or returns a different count
        """
        # --- parse ---
        try:
            payload = response.json()
        except ValueError as exc:  # a 200 whose body is not JSON — a proxy error page, typically
            raise EmbeddingError("Embedder returned a non-JSON body") from exc

        vectors = payload.get("vectors")

        if vectors is None:
            raise EmbeddingError("Embedder response has no 'vectors' field")

        # --- count ---
        # One vector per text, in order, is the whole contract callers rely on: retrieval zips
        # these back onto the tickets they came from. A mismatch would misattribute vectors to
        # tickets — wrong answers rather than an error, so it has to be caught here.
        if len(vectors) != expected:
            raise EmbeddingError(
                f"Embedder returned {len(vectors)} vector(s) for {expected} text(s)"
            )

        return vectors
