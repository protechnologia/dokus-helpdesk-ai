import logging

from sentence_transformers import SentenceTransformer
from starlette.concurrency import run_in_threadpool

from embedder_app.encoding.base import Encoder
from embedder_app.encoding.errors import EncoderError
from embedder_app.models import EmbeddingMode

logger = logging.getLogger(__name__)

# What each mode prepends to the input text. This is the single most dangerous mapping in the
# project: the same text under a different prefix yields a DIFFERENT vector, and mixing modes
# inside one vector space silently destroys retrieval quality (CLAUDE.md -> "Embeddingi").
#
# The values are PolDense's own convention, taken from its `config_sentence_transformers.json`
# (`[query]: ` for queries, empty for documents) plus `[sts]: ` for symmetric ticket-to-ticket
# comparison. Rival models measured in stage 3 use different conventions — Nomic wants
# `search_query: ` / `search_document: `, BGE-M3 wants none at all — so whoever adds a model here
# must revisit this table rather than assume it transfers.
MODE_PREFIXES: dict[EmbeddingMode, str] = {
    "query":   "[query]: ",
    "passage": "",
    "sts":     "[sts]: ",
}


class SentenceTransformerEncoder(Encoder):
    """
    Description:
    The real backend (`EMBEDDING_BACKEND=sentence-transformers`): loads a local Polish embedding
    model through `sentence-transformers` and turns ticket text into vectors. The ONLY module in
    the project allowed to import that library (CLAUDE.md -> "Don't"), which is what makes
    swapping PolDense for mmlw or BGE-M3 an ENV change rather than a code change.

    Flow:
        1. The factory builds it once per process with the model name from `EMBEDDING_MODEL`;
           the constructor downloads/loads the weights and asks the model its own dimension.
        2. `encode()` prepends the prefix that `mode` means FOR THIS MODEL (see `MODE_PREFIXES`),
           runs one batched forward pass and returns unit-length vectors.
        3. Inference is offloaded to a worker thread — `sentence-transformers` is synchronous and
           would otherwise block the event loop for the whole batch.

    Vectors are normalised HERE rather than left as the model produces them: PolDense ships no
    `Normalize` module, while `FakeEncoder` yields unit vectors by construction. Without this the
    two backends would land cosine scores in different ranges, and `RAG_SCORE_MIN` would mean one
    thing in tests and another in production.
    """

    def __init__(
        self,
        model_name: str,  # e.g. "OPI-PIB/PolDense-150M"
    ):
        """
        Description:
        Loads the model and records the dimension it reports. Deliberately eager: weights are
        loaded at startup so a missing model or a wrong name kills the service immediately,
        instead of surfacing on the first request an hour into an indexing run.

        Example args:
            model_name="OPI-PIB/PolDense-150M"

        Example result:
            SentenceTransformerEncoder wrapping a 768-dimensional PolDense model

        Raises:
            EncoderError: the model could not be loaded (unknown name, no weights, no disk space)
        """
        self._model_name = model_name

        # --- load weights ---
        # OSError covers the whole family of load failures (network, missing files, bad cache);
        # ValueError is what `sentence-transformers` raises for a name it cannot resolve. Both are
        # re-raised as our own error so nothing above this line imports the library's exceptions.
        try:
            self._model = SentenceTransformer(model_name)
        except (
            OSError,     # weights unreachable, corrupt cache, no space on device
            ValueError,  # the library cannot resolve this model name
        ) as exc:
            raise EncoderError(f"Could not load embedding model {model_name!r}: {exc}") from exc

        # --- dimension ---
        # Asked of the model rather than taken from configuration: the factory compares this
        # answer against EMBEDDING_VECTOR_SIZE, and a check reading the same setting twice would
        # confirm nothing. `get_embedding_dimension` is the current name — the older
        # `get_sentence_embedding_dimension` still works but warns.
        dimension = self._model.get_embedding_dimension()

        if dimension is None:
            raise EncoderError(f"Model {model_name!r} does not report an embedding dimension")

        self._dimension = dimension

        logger.info("loaded embedding model=%s dimension=%d", model_name, dimension)

    @property
    def model_name(self) -> str:
        """
        Description:
        Names the model behind every response, so a Qdrant collection stays traceable to what
        built it — vectors from two different models are not comparable, and the collection is
        bound to one of them.

        Example args:
            (none)

        Example result:
            "OPI-PIB/PolDense-150M"
        """
        return self._model_name

    @property
    def dimension(self) -> int:
        """
        Description:
        Returns the width the loaded model actually produces, as reported by the model itself.

        Example args:
            (none)

        Example result:
            768
        """
        return self._dimension

    async def encode(
        self,
        texts: list[str],      # e.g. ["Drukarka nie drukuje po aktualizacji"]
        mode:  EmbeddingMode,  # e.g. "passage"
    ) -> list[list[float]]:
        """
        Description:
        Embeds a batch of texts in one mode and returns unit-length vectors in the order received.

        Example args:
            texts=["Drukarka nie drukuje po aktualizacji"]
            mode="passage"

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EncoderError: inference failed (out of memory, model in a broken state)
        """
        self._log_call(texts, mode)

        prefixed = [f"{MODE_PREFIXES[mode]}{text}" for text in texts]

        # --- inference ---
        # Off the event loop: the library is synchronous and a batch of a few hundred texts blocks
        # for seconds on CPU, which would stall every other request this service is serving.
        return await run_in_threadpool(self._encode_sync, prefixed)

    def _encode_sync(
        self,
        prefixed: list[str],  # e.g. ["[query]: Drukarka nie drukuje"]
    ) -> list[list[float]]:
        """
        Description:
        Runs the blocking forward pass. Split out so the thread-offload above stays one readable
        line, and so the library's failure modes are translated in exactly one place.

        Example args:
            prefixed=["[query]: Drukarka nie drukuje"]

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EncoderError: the model failed to produce vectors
        """
        # `normalize_embeddings` is what puts the vectors on the unit sphere — see the class
        # docstring for why this cannot be left to the model. `convert_to_numpy` keeps the return
        # type predictable; `.tolist()` then hands plain floats to Pydantic.
        try:
            vectors = self._model.encode(
                prefixed,
                normalize_embeddings = True,
                convert_to_numpy     = True,
            )
        except RuntimeError as exc:  # torch raises this for OOM and for a model in a bad state
            raise EncoderError(f"Encoding failed on {len(prefixed)} text(s): {exc}") from exc

        return vectors.tolist()
