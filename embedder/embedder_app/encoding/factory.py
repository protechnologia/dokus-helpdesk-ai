from functools import lru_cache

from embedder_app.config import Settings, get_settings
from embedder_app.encoding.base import Encoder
from embedder_app.encoding.errors import EncoderConfigError
from embedder_app.encoding.fake import FakeEncoder

BACKEND_FAKE = "fake"

# Only the offline fake exists so far. A local `sentence-transformers` backend (PolDense, and the
# rival models it is measured against in stage 3) joins the tuple in stage 2 — the abstraction is
# here earlier so nobody imports a model library straight into a router in the meantime.
SUPPORTED_BACKENDS = (BACKEND_FAKE,)


def build_encoder(settings: Settings) -> Encoder:   # e.g. Settings(embedding_backend="fake")
    """
    Description:
    Builds the encoder named by `EMBEDDING_BACKEND`. Fails fast: an unknown backend (or, later, a
    real one lacking its model name, or reporting a dimension other than the configured one)
    raises here, at construction time, instead of surfacing as vectors of the wrong width that
    Qdrant rejects an hour into an indexing run.

    Example args:
        settings=Settings(embedding_backend="fake", embedding_vector_size=768)

    Example result:
        FakeEncoder(dimension=768)

    Raises:
        EncoderConfigError: `EMBEDDING_BACKEND` names a backend this build does not implement
    """
    # ENV values arrive as typed by a human: case and stray spaces must not decide the backend.
    backend = settings.embedding_backend.strip().lower()

    if backend == BACKEND_FAKE:
        return FakeEncoder(dimension=settings.embedding_vector_size)

    supported = ", ".join(SUPPORTED_BACKENDS)

    raise EncoderConfigError(
        f"Unknown EMBEDDING_BACKEND={settings.embedding_backend!r}; supported: {supported}"
    )


@lru_cache
def get_encoder() -> Encoder:
    """
    Description:
    Provides the process-wide encoder, built once and shared by every request. Caching is not an
    optimisation detail here: a real backend loads model weights, which must happen once per
    process rather than per request. Separate from `build_encoder()` so tests can exercise the
    configuration rules without touching the cached instance.

    Example args:
        (none)

    Example result:
        FakeEncoder(dimension=768)

    Raises:
        EncoderConfigError: the configured backend cannot be built
    """
    return build_encoder(get_settings())
