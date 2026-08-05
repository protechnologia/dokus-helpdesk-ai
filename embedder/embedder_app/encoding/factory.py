from functools import lru_cache

from embedder_app.config import Settings, get_settings
from embedder_app.encoding.base import Encoder
from embedder_app.encoding.errors import EncoderConfigError
from embedder_app.encoding.fake import FakeEncoder
from embedder_app.encoding.sentence_transformer import SentenceTransformerEncoder

BACKEND_FAKE                  = "fake"
BACKEND_SENTENCE_TRANSFORMERS = "sentence-transformers"

# Two backends, and the second one covers every real model: PolDense, mmlw and BGE-M3 all load
# through `sentence-transformers`, so they differ by EMBEDDING_MODEL rather than by code. Naming
# the backend after the library instead of after a model is what keeps stage 3 (which compares
# those models) a matter of configuration.
SUPPORTED_BACKENDS = (BACKEND_FAKE, BACKEND_SENTENCE_TRANSFORMERS)


def _build_sentence_transformer_encoder(
    settings: Settings,  # e.g. Settings(embedding_model="OPI-PIB/PolDense-150M")
) -> SentenceTransformerEncoder:
    """
    Description:
    Builds the real encoder, refusing first to load anything without a model name. The name is
    optional in `Settings` (the shipped backend is the fake, which has no model), so the
    requirement is enforced here — at the only point where it is real.

    Example args:
        settings=Settings(embedding_backend="sentence-transformers",
                          embedding_model="OPI-PIB/PolDense-150M")

    Example result:
        SentenceTransformerEncoder(model_name="OPI-PIB/PolDense-150M")

    Raises:
        EncoderConfigError: `EMBEDDING_MODEL` is missing
        EncoderError: the model could not be loaded
    """
    model = settings.embedding_model.strip()

    if not model:
        raise EncoderConfigError(
            f"EMBEDDING_BACKEND={BACKEND_SENTENCE_TRANSFORMERS!r} "
            f"wymaga ustawienia: EMBEDDING_MODEL"
        )

    return SentenceTransformerEncoder(model_name=model)


def _verify_dimension(
    encoder:  Encoder,  # e.g. SentenceTransformerEncoder(model_name="OPI-PIB/PolDense-150M")
    expected: int,      # e.g. 768 — the configured EMBEDDING_VECTOR_SIZE
) -> None:
    """
    Description:
    Refuses an encoder whose vectors are not as wide as configured. The dimension is a contract
    with the Qdrant collection, and the two sources of it are independent: the model measures
    itself, `EMBEDDING_VECTOR_SIZE` is typed by a human. Catching the disagreement at startup is
    the whole point — otherwise it surfaces as Qdrant rejecting points an hour into an indexing
    run, long after the LLM parsing that fed it was paid for.

    Example args:
        encoder=SentenceTransformerEncoder(model_name="OPI-PIB/PolDense-150M")
        expected=1024

    Example result:
        None  # returns quietly when the model agrees with the configuration

    Raises:
        EncoderConfigError: the model's dimension differs from the configured one
    """
    if encoder.dimension == expected:
        return

    # Both numbers AND the model name: "768 != 1024" alone does not say which side to correct.
    raise EncoderConfigError(
        f"Model {encoder.model_name!r} zwraca wektory o wymiarze {encoder.dimension}, "
        f"a EMBEDDING_VECTOR_SIZE={expected}"
    )


def build_encoder(settings: Settings) -> Encoder:   # e.g. Settings(embedding_backend="fake")
    """
    Description:
    Builds the encoder named by `EMBEDDING_BACKEND`. Fails fast: an unknown backend, a real one
    lacking its model name, or a model whose width contradicts `EMBEDDING_VECTOR_SIZE` raises
    here, at construction time, instead of surfacing as vectors of the wrong width that Qdrant
    rejects an hour into an indexing run.

    Example args:
        settings=Settings(embedding_backend="fake", embedding_vector_size=768)

    Example result:
        FakeEncoder(dimension=768)

    Raises:
        EncoderConfigError: unknown backend, missing `EMBEDDING_MODEL`, or a dimension mismatch
        EncoderError: the model named by `EMBEDDING_MODEL` could not be loaded
    """
    # ENV values arrive as typed by a human: case and stray spaces must not decide the backend.
    backend = settings.embedding_backend.strip().lower()

    if backend == BACKEND_FAKE:
        # No dimension check: the fake is TOLD its width by the same setting, so comparing the two
        # would confirm nothing. The check starts to matter once a model measures itself.
        return FakeEncoder(dimension=settings.embedding_vector_size)

    if backend == BACKEND_SENTENCE_TRANSFORMERS:
        encoder = _build_sentence_transformer_encoder(settings)

        _verify_dimension(encoder, settings.embedding_vector_size)

        return encoder

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
