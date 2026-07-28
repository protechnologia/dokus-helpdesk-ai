import pytest

from embedder_app.config import Settings
from embedder_app.encoding import EncoderConfigError, EncoderError, FakeEncoder, build_encoder


def _settings(backend: str, vector_size: int = 768) -> Settings:   # e.g. "fake"
    """
    Description:
    Builds Settings with an explicit backend, so the assertions cannot be moved by a variable
    exported in the developer's shell (an init argument outranks the environment).

    Example args:
        backend="fake"
        vector_size=768

    Example result:
        Settings(embedding_backend="fake", embedding_vector_size=768)
    """
    return Settings(embedding_backend=backend, embedding_vector_size=vector_size)


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
        build_encoder(_settings("local"))


def test_config_error_names_the_offending_value() -> None:
    """Error message quotes the rejected value → the operator sees what to fix in .env."""
    with pytest.raises(EncoderConfigError, match="poldense"):
        build_encoder(_settings("poldense"))


def test_config_error_is_catchable_as_the_layer_error() -> None:
    """EncoderConfigError is an EncoderError → callers catch one type for the whole layer."""
    with pytest.raises(EncoderError):
        build_encoder(_settings("local"))
