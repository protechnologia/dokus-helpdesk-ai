import hashlib
import math
from random import Random

from embedder_app.encoding.base import Encoder
from embedder_app.models import EmbeddingMode

# Reported as the model in every response. Matches FAKE_MODEL_NAME on the LLM side on purpose:
# one word means "offline default, nothing real behind it" across the whole project. It must not
# look like a model id — vectors from the fake and from PolDense are not comparable, and whoever
# indexed them has to be able to tell afterwards which ones they got.
FAKE_MODEL_NAME = "fake"


class FakeEncoder(Encoder):
    """
    Description:
    The default backend (`EMBEDDING_BACKEND=fake`) and the one every test runs against. Loads no
    weights and needs no GPU, so `docker compose up` and `pytest` work offline and instantly —
    the same bargain `FakeLLMClient` makes on the LLM side.

    Flow:
        1. The factory builds it with the dimension taken from `EMBEDDING_VECTOR_SIZE` — having
           no model to ask, this backend can only be TOLD how wide its vectors are.
        2. `encode()` maps each text through `deterministic_vector()` and logs the call.
        3. `mode` is validated by the request model and then IGNORED: with no trained prefixes
           there is nothing to apply. Stage 2 gives the real encoder actual prefixes.

    Semantically meaningless by design: similar texts get unrelated vectors. That is what makes
    it a good test double (thresholds, dedupe and routing stop depending on model weights) and
    what makes it useless for stage 3, where recall@5 is measured against real models.
    """

    def __init__(
        self,
        dimension: int,  # e.g. 768
    ):
        """
        Description:
        Stores the vector width this encoder will produce.

        Example args:
            dimension=768

        Example result:
            FakeEncoder producing 768-dimensional unit vectors
        """
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        """
        Description:
        Names the backend in every response, so a collection built from fake vectors is
        recognisable as such long after the run that produced it.

        Example args:
            (none)

        Example result:
            "fake"
        """
        return FAKE_MODEL_NAME

    @property
    def dimension(self) -> int:
        """
        Description:
        Returns the configured width. Unlike a real model, this backend has nothing to measure —
        the number comes from configuration, which is why the factory's dimension check cannot
        fail here and starts to matter only in stage 2.

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
        Produces one vector per text, in the order received. No I/O and no thread offload — the
        coroutine is async only to keep the signature a real backend will need.

        Example args:
            texts=["Drukarka nie drukuje po aktualizacji"]
            mode="passage"

        Example result:
            [[0.0123, -0.0456, …]]
        """
        self._log_call(texts, mode)

        return [deterministic_vector(text, self._dimension) for text in texts]


def deterministic_vector(
    text:      str,  # e.g. "Drukarka nie drukuje po aktualizacji"
    dimension: int,  # e.g. 768
) -> list[float]:
    """
    Description:
    Fabricates a stable vector for a text. The same text always yields the same vector, in this
    process and in any other, so thresholds, dedupe and routing can be tested without a model
    (CLAUDE.md -> "Testy"). A module-level pure function rather than a method: it is the part of
    this backend testable without an instance, and it is what stage 2 replaces wholesale.

    Example args:
        text="Drukarka nie drukuje po aktualizacji"
        dimension=4

    Example result:
        [0.31, -0.77, 0.12, 0.54]   # unit length
    """
    # --- seed: sha256, NOT the built-in hash() ---
    # hash() is salted per process (PYTHONHASHSEED), so the same ticket would embed one way at
    # indexing time and another way at query time — the very bug this backend exists to preclude.
    digest = hashlib.sha256(text.encode("utf-8")).digest()

    # --- components ---
    # Mersenne Twister seeded with a fixed integer is reproducible across processes, platforms and
    # Python builds. Only `.random()` is documented as stable, hence uniform draws mapped to
    # [-1, 1) instead of the more natural-looking `rng.gauss()`.
    rng        = Random(int.from_bytes(digest, "big"))
    components = [rng.random() * 2.0 - 1.0 for _ in range(dimension)]

    # --- normalise ---
    # Real sentence embeddings live on the unit sphere, so cosine scores land in a familiar range;
    # a fake with arbitrary magnitudes would make RAG_SCORE_MIN mean something different in tests
    # than in production.
    norm = math.sqrt(sum(component * component for component in components))

    return [component / norm for component in components]
