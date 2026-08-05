import pytest

from embedder_app.config import Settings
from embedder_app.encoding import EncoderConfigError, EncoderError, FakeEncoder, build_encoder
from embedder_app.encoding.factory import _verify_dimension


def _settings(
    backend:     str,       # e.g. "fake"
    vector_size: int = 768,
    model:       str = "",  # e.g. "OPI-PIB/PolDense-150M"
) -> Settings:
    """
    Description:
    Builds Settings with an explicit backend, so the assertions cannot be moved by a variable
    exported in the developer's shell (an init argument outranks the environment).

    Example args:
        backend="fake"
        vector_size=768
        model=""

    Example result:
        Settings(embedding_backend="fake", embedding_vector_size=768)
    """
    return Settings(
        embedding_backend     = backend,
        embedding_model       = model,
        embedding_vector_size = vector_size,
    )


def test_default_backend_builds_the_offline_fake() -> None:
    """EMBEDDING_BACKEND=fake (the shipped default) → FakeEncoder, so no weights are needed."""
    encoder = build_encoder(_settings("fake"))

    assert isinstance(encoder, FakeEncoder)


def test_backend_name_is_read_case_and_space_insensitively() -> None:
    """Backend typed as "  FAKE " in .env → same encoder; casing must not decide the backend."""
    encoder = build_encoder(_settings("  FAKE "))

    assert isinstance(encoder, FakeEncoder)


def test_encoder_is_built_with_the_configured_dimension() -> None:
    """EMBEDDING_VECTOR_SIZE → the encoder's width, because the fake has no model to ask."""
    encoder = build_encoder(_settings("fake", vector_size=1024))

    assert encoder.dimension == 1024


def test_unimplemented_backend_fails_at_build_time() -> None:
    """Backend this build has no encoder for → EncoderConfigError at startup, not at request."""
    with pytest.raises(EncoderConfigError):
        build_encoder(_settings("onnx"))


def test_config_error_names_the_offending_value() -> None:
    """Error message quotes the rejected value → the operator sees what to fix in .env."""
    with pytest.raises(EncoderConfigError, match="poldense"):
        build_encoder(_settings("poldense"))


def test_config_error_is_catchable_as_the_layer_error() -> None:
    """EncoderConfigError is an EncoderError → callers catch one type for the whole layer."""
    with pytest.raises(EncoderError):
        build_encoder(_settings("onnx"))


def test_real_backend_without_a_model_name_fails_at_build_time() -> None:
    """sentence-transformers with no EMBEDDING_MODEL → EncoderConfigError before any download."""
    with pytest.raises(EncoderConfigError, match="EMBEDDING_MODEL"):
        build_encoder(_settings("sentence-transformers"))


def test_real_backend_rejects_a_whitespace_only_model_name() -> None:
    """EMBEDDING_MODEL=" " → treated as missing, not as a model literally named one space."""
    with pytest.raises(EncoderConfigError, match="EMBEDDING_MODEL"):
        build_encoder(_settings("sentence-transformers", model="   "))


# The dimension check reads two properties and nothing else, so `FakeEncoder` — which is TOLD its
# width — stands in for the real model here. Loading weights to assert on an integer would make a
# unit test download hundreds of megabytes.
def test_dimension_mismatch_is_refused_at_build_time() -> None:
    """Encoder 768 wide vs EMBEDDING_VECTOR_SIZE=1024 → refused at startup, not by Qdrant later."""
    with pytest.raises(EncoderConfigError):
        _verify_dimension(FakeEncoder(dimension=768), expected=1024)


def test_dimension_mismatch_message_names_both_numbers() -> None:
    """Mismatch message quotes encoder width AND configured width → the reader knows what to fix."""
    with pytest.raises(EncoderConfigError, match="768.*1024"):
        _verify_dimension(FakeEncoder(dimension=768), expected=1024)


def test_matching_dimension_passes_quietly() -> None:
    """Encoder width equal to the configured one → no exception, the encoder is accepted."""
    _verify_dimension(FakeEncoder(dimension=768), expected=768)
