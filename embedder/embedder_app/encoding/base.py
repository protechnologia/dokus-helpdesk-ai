import logging
from abc import ABC, abstractmethod

from embedder_app.models import EmbeddingMode

logger = logging.getLogger(__name__)


class Encoder(ABC):
    """
    Description:
    The only way this service turns text into vectors. Concrete subclasses wrap exactly one
    backend and are the ONLY place its library may be imported (`sentence-transformers` never
    appears outside them), so swapping the fake for PolDense — or PolDense for BGE-M3 — is a
    configuration change rather than a code change.

    Flow:
        1. `get_encoder()` (see `factory.py`) builds the implementation named by
           `EMBEDDING_BACKEND` and fails fast when its configuration is incomplete.
        2. The router calls `encode()` with the texts and the mode taken from the request.
        3. The implementation applies whatever the mode means FOR THAT MODEL and returns one
           vector per text, reporting the call through `_log_call()`.

    Why the mode is handed to the implementation rather than resolved earlier: the mapping
    "mode -> prefix" is a property of the model, not of the protocol. PolDense prepends
    `[query]: ` / nothing / `[sts]: `, mmlw uses its own convention and BGE-M3 has no prefixes at
    all. The HTTP contract therefore speaks of query/passage/sts, never of a prefix string.

    Implementations are async: real inference is synchronous and CPU/GPU-bound, so it has to be
    offloaded to a worker thread — an async signature here means the router does not change when
    the fake is replaced by a model that actually blocks.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Description:
        Identifies what produced the vectors. Travels back in every response because a Qdrant
        collection is bound to one model: whoever stores these vectors must be able to see that
        they came from the fake backend and not from PolDense.

        Example args:
            (none)

        Example result:
            "fake"
        """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Description:
        Width of the vectors this encoder produces. It is a contract with the Qdrant collection,
        so it is exposed rather than assumed: a real model knows its own dimension, and the
        factory checks that answer against the configured one.

        Example args:
            (none)

        Example result:
            768
        """

    @abstractmethod
    async def encode(
        self,
        texts: list[str],      # e.g. ["Drukarka nie drukuje po aktualizacji"]
        mode:  EmbeddingMode,  # e.g. "passage"
    ) -> list[list[float]]:
        """
        Description:
        Encodes a batch of texts in ONE mode and returns the vectors in the order received. Batch
        rather than single text, because real models amortise a batch over one forward pass.

        Example args:
            texts=["Drukarka nie drukuje po aktualizacji"]
            mode="passage"

        Example result:
            [[0.0123, -0.0456, …]]

        Raises:
            EncoderError: the backend failed to produce vectors
        """

    def _log_call(
        self,
        texts: list[str],      # e.g. ["Drukarka nie drukuje po aktualizacji"]
        mode:  EmbeddingMode,  # e.g. "passage"
    ) -> None:
        """
        Description:
        Emits the accounting line for one encoding call, in one shape for every backend. The
        texts themselves go to DEBUG only — they are ticket content, i.e. customer data
        (CLAUDE.md -> "Logi i obserwowalność"); INFO sees counts and identifiers exclusively.

        Example args:
            texts=["Drukarka nie drukuje po aktualizacji"]
            mode="passage"

        Example result:
            None — one INFO record with counts, one DEBUG record with the texts
        """
        logger.info(
            "encode model=%s mode=%s batch_size=%d dimension=%d",
            self.model_name,
            mode,
            len(texts),
            self.dimension,
        )
        logger.debug("encode texts=%r", texts)
