import logging

import httpx

from app.retrieval.errors import RetrievalConfigError, RetrievalError
from app.retrieval.model_point import VECTOR_PROBLEM, VECTOR_STS, TicketPoint

logger = logging.getLogger(__name__)

# Distance metric for both named vectors. Cosine because the embedder returns L2-normalised
# vectors (normalisation is OUR job — PolDense ships no Normalize module, see CLAUDE.md ->
# "Embeddingi"), and on unit vectors cosine is the metric the stage-3 measurement used. Switching
# it would make RAG_SCORE_MIN mean something different from what was measured.
DISTANCE = "Cosine"

# How many points go in one upsert request. Large enough that a 1500-record corpus is a handful of
# calls, small enough that one failure does not lose a long run's worth of work.
UPSERT_BATCH_SIZE = 64


class QdrantClient:
    """
    Description:
    How `api` talks to the Qdrant index: collection lifecycle and writes. "Client" means a process
    boundary is crossed (CLAUDE.md -> "Warstwy kodu") — this speaks HTTP to a service we did not
    write, so every failure of that conversation stops here and becomes a `RetrievalError`.

    Do czego:
    Qdrant is the index, never the source of truth (rule 8): everything here must be reproducible
    from `data/parsed/` with one command, which is why deleting a collection is an ordinary
    operation rather than a disaster.

    Flow:
        1. Built once from `Settings` (URL, collection name, timeout) and reused.
        2. `ensure_collection()` creates the collection with both named vectors, or verifies that
           an existing one matches — it never adapts to a mismatch.
        3. `upsert_points()` writes batches of `TicketPoint`.
        4. `delete_collection()` / `count_points()` support rebuild and reporting.

    Written directly on the REST API rather than on `qdrant-client`: the endpoints used here are
    few, `httpx` is already a dependency, and an abstraction layer would hide exactly what this
    project controls by hand — named vectors, prefixes, thresholds (CLAUDE.md -> "Świadomie
    pominięte", the same reasoning that excluded LangChain/LlamaIndex).
    """

    def __init__(
        self,
        base_url:   str,           # e.g. "http://qdrant:6333"
        collection: str,           # e.g. "tickets"
        timeout:    float = 30.0,  # seconds
    ):
        """
        Description:
        Builds the client for one Qdrant instance and one collection. Refuses empty values: those
        are what `docker compose` substitutes for an unset variable, and a client built on them
        fails later with an unreadable relative-URL error, far from the cause.

        Example args:
            base_url="http://qdrant:6333"
            collection="tickets"
            timeout=30.0

        Example result:
            QdrantClient writing to http://qdrant:6333/collections/tickets

        Raises:
            RetrievalConfigError: `QDRANT_URL` or `QDRANT_COLLECTION` is empty
        """
        # Guards, not politeness — see the class docstring on compose substituting "".
        if not base_url.strip():
            raise RetrievalConfigError("QDRANT_URL nie może być puste")

        if not collection.strip():
            raise RetrievalConfigError("QDRANT_COLLECTION nie może być puste")

        self._collection = collection.strip()
        self._client     = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # a trailing slash would double up with the paths
            timeout  = timeout,
        )

    @property
    def collection(self) -> str:
        """
        Description:
        Names the collection this client writes to. Exposed because callers report it (the CLI
        prints it, logs carry it) and should not have to remember what they configured.

        Example args:
            (none)

        Example result:
            "tickets"
        """
        return self._collection

    async def ensure_collection(
        self,
        vector_size: int,  # e.g. 768 — must equal EMBEDDING_VECTOR_SIZE
    ) -> bool:
        """
        Description:
        Makes sure the collection exists with both named vectors at the given size. Returns True
        when it had to be created, False when a matching one was already there — the caller
        reports which happened, it does not decide anything.

        Deliberately does NOT repair a mismatch. A collection whose vectors are a different size
        or carry different names was built for another model, and silently adapting would produce
        an index nobody can compare against (CLAUDE.md -> "Embeddingi": changing the model means a
        NEW collection, not a migration).

        Example args:
            vector_size=768

        Example result:
            True — the collection did not exist and was created

        Raises:
            RetrievalConfigError: an existing collection contradicts `vector_size` or the schema
            RetrievalError: Qdrant is unreachable or answered with an error
        """
        existing = await self._get_collection()

        # --- already there: verify, never adapt ---
        if existing is not None:
            self._verify_schema(existing, vector_size)

            return False

        # --- create ---
        logger.info(
            "creating collection=%s vector_size=%d vectors=%s",
            self._collection,
            vector_size,
            (VECTOR_PROBLEM, VECTOR_STS),
        )
        await self._request(
            "PUT",
            f"/collections/{self._collection}",
            json={
                "vectors": {
                    VECTOR_PROBLEM: {"size": vector_size, "distance": DISTANCE},
                    VECTOR_STS:     {"size": vector_size, "distance": DISTANCE},
                },
            },
        )

        return True

    async def upsert_points(
        self,
        points: list[TicketPoint],  # e.g. [TicketPoint(point_id="3f2a…", …)]
    ) -> int:
        """
        Description:
        Writes points to the collection, in batches, and returns how many were written. Upsert
        rather than insert: point ids are derived from `ticket_id`, so re-running an index build
        overwrites the same points instead of duplicating the corpus.

        Waits for each batch to be applied (`wait=true`). An indexing run reports what it wrote
        and a later step reads it back, so "accepted, will apply eventually" would make both lie.

        Example args:
            points=[TicketPoint(point_id="3f2a1c9e-…", …)]

        Example result:
            1

        Raises:
            RetrievalError: Qdrant is unreachable, or rejected a batch (a vector-size mismatch
                            surfaces here as an error response, not as a silent drop)
        """
        # Nothing to do — but say so, because "0 written" is a legitimate outcome of a filter that
        # rejected everything, and a caller must be able to tell that from a crash.
        if not points:
            logger.info("upsert collection=%s points=0 — nothing to write", self._collection)

            return 0

        written = 0

        for start in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[start : start + UPSERT_BATCH_SIZE]

            await self._request(
                "PUT",
                f"/collections/{self._collection}/points",
                params = {"wait": "true"},
                json   = {"points": [point.to_qdrant() for point in batch]},
            )

            written += len(batch)

        # Counts only: payloads hold ticket content, i.e. customer data, which belongs to DEBUG at
        # most (CLAUDE.md -> "Logi i obserwowalność").
        logger.info("upsert collection=%s points=%d", self._collection, written)

        return written

    async def delete_collection(self) -> bool:
        """
        Description:
        Drops the collection. Returns True when one was actually removed, False when there was
        nothing to remove — `index rebuild` needs to report which, and an absent collection is a
        normal starting state, not an error.

        Safe by design rather than by care: the index is rebuildable from `data/parsed/` with one
        command (rule 8), so this destroys a derivative, never the artifact.

        Example args:
            (none)

        Example result:
            True — a collection existed and is gone

        Raises:
            RetrievalError: Qdrant is unreachable or answered with an error
        """
        if await self._get_collection() is None:
            return False

        logger.info("deleting collection=%s", self._collection)
        await self._request("DELETE", f"/collections/{self._collection}")

        return True

    async def count_points(self) -> int:
        """
        Description:
        Counts points in the collection. Used by the indexing report and by tests asserting that
        two rebuilds land on the same state.

        Example args:
            (none)

        Example result:
            200

        Raises:
            RetrievalError: Qdrant is unreachable, answered with an error, or the collection does
                            not exist
        """
        payload = await self._request(
            "POST",
            f"/collections/{self._collection}/points/count",
            json={"exact": True},  # approximate counts would make a rebuild assertion flaky
        )

        return payload["result"]["count"]

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

    async def _get_collection(self) -> dict | None:
        """
        Description:
        Reads the collection description, or returns None when it does not exist. A missing
        collection is an ordinary state here — every caller has a sensible answer for it — so it
        is a return value rather than an exception.

        Example args:
            (none)

        Example result:
            {"result": {"config": {"params": {"vectors": {"problem": {"size": 768}, …}}}}}

        Raises:
            RetrievalError: Qdrant is unreachable, or answered with a status other than 200/404
        """
        try:
            response = await self._client.get(f"/collections/{self._collection}")
        except httpx.TimeoutException as exc:      # Qdrant did not answer in time
            raise RetrievalError(f"Qdrant timed out reading '{self._collection}'") from exc
        except httpx.HTTPError as exc:             # connection refused, DNS, broken transport
            raise RetrievalError(f"Could not reach Qdrant: {exc}") from exc

        # The one status that is an answer rather than a failure: no such collection yet.
        if response.status_code == 404:
            return None

        if response.status_code >= 400:
            raise RetrievalError(
                f"Qdrant returned HTTP {response.status_code} reading '{self._collection}'"
            )

        return self._decode(response)

    def _verify_schema(
        self,
        description: dict,  # e.g. {"result": {"config": {"params": {"vectors": {…}}}}}
        vector_size: int,   # e.g. 768
    ) -> None:
        """
        Description:
        Checks an existing collection against the configuration we are about to write with. Both
        named vectors must be present and both must have the expected size.

        Why this is worth its own method: without it a mismatch shows up as points rejected by
        Qdrant an hour into an indexing run — after the expensive LLM parsing has been paid for
        (CLAUDE.md -> "Warstwa embeddera", the same reasoning as the dimension check there). The
        message names BOTH numbers, because "768 != 1024" alone does not say which side to fix.

        Example args:
            description={"result": {"config": {"params": {"vectors": {"problem": {"size": 768}}}}}}
            vector_size=768

        Example result:
            None — the collection matches

        Raises:
            RetrievalConfigError: a named vector is missing or has a different size
        """
        # Defaults rather than indexing: a shape we do not recognise must produce OUR message
        # naming the collection, not a KeyError from three levels down.
        vectors = (
            description.get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
        )

        for name in (VECTOR_PROBLEM, VECTOR_STS):
            declared = vectors.get(name)

            # A collection built before `sts` existed, or under a different schema entirely.
            if declared is None:
                raise RetrievalConfigError(
                    f"kolekcja '{self._collection}' nie ma named vectora '{name}' "
                    f"(ma: {', '.join(sorted(vectors)) or 'brak'}) — skasuj ją i odbuduj "
                    f"(`helpdesk index rebuild`)"
                )

            actual = declared.get("size")

            if actual != vector_size:
                raise RetrievalConfigError(
                    f"kolekcja '{self._collection}' ma wektor '{name}' o wymiarze {actual}, "
                    f"a EMBEDDING_VECTOR_SIZE={vector_size} — zmiana modelu wymaga NOWEJ "
                    f"kolekcji, nie migracji"
                )

    async def _request(
        self,
        method: str,           # e.g. "PUT"
        path:   str,           # e.g. "/collections/tickets"
        params: dict | None = None,
        json:   dict | None = None,
    ) -> dict:
        """
        Description:
        Performs one call and returns the decoded body. The single place where transport failures
        become `RetrievalError`, so no caller ever sees an `httpx` type (rule 4).

        Example args:
            method="PUT"
            path="/collections/tickets"
            json={"vectors": {"problem": {"size": 768, "distance": "Cosine"}}}

        Example result:
            {"result": True, "status": "ok"}

        Raises:
            RetrievalError: transport failed, the service answered non-2xx, or the body was not
                            the JSON the contract promises
        """
        try:
            response = await self._client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.TimeoutException as exc:       # did not answer in time
            raise RetrievalError(f"Qdrant timed out on {method} {path}") from exc
        except httpx.HTTPStatusError as exc:        # answered, but with a non-2xx status
            # Qdrant explains rejections in the body (wrong vector size, unknown vector name), and
            # that text is ours rather than the customer's — worth carrying into the message.
            raise RetrievalError(
                f"Qdrant returned HTTP {exc.response.status_code} on {method} {path}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:              # connection refused, DNS, broken transport
            raise RetrievalError(f"Could not reach Qdrant: {exc}") from exc

        return self._decode(response)

    def _decode(
        self,
        response: httpx.Response,  # e.g. 200 with {"result": {...}, "status": "ok"}
    ) -> dict:
        """
        Description:
        Turns a successful response into a dict. Separate from the call so that "the body is not
        what we expect" is one failure with one message, wherever it happens.

        Example args:
            response=<Response [200 OK]>

        Example result:
            {"result": {"status": "green"}, "status": "ok"}

        Raises:
            RetrievalError: the body is not JSON, or is not a JSON object
        """
        try:
            payload = response.json()
        except ValueError as exc:  # a 200 whose body is not JSON — a proxy error page, typically
            raise RetrievalError("Qdrant returned a non-JSON body") from exc

        if not isinstance(payload, dict):
            raise RetrievalError(f"Qdrant returned {type(payload).__name__}, expected an object")

        return payload
