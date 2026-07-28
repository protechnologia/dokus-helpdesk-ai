from embedder_app.encoding import FakeEncoder, deterministic_vector

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


async def test_encode_returns_one_vector_per_text() -> None:
    """Batch of two texts → two vectors, in the order they were submitted."""
    encoder = FakeEncoder(dimension=16)

    vectors = await encoder.encode([TICKET_TEXT, OTHER_TICKET_TEXT], "passage")

    assert vectors == [
        deterministic_vector(TICKET_TEXT, 16),
        deterministic_vector(OTHER_TICKET_TEXT, 16),
    ]


async def test_encode_uses_the_configured_dimension() -> None:
    """Encoder built with a dimension → every vector is exactly that wide."""
    encoder = FakeEncoder(dimension=32)

    vectors = await encoder.encode([TICKET_TEXT], "query")

    assert len(vectors[0]) == 32


async def test_mode_does_not_change_the_vector() -> None:
    """Same text in query/passage/sts → identical vectors (this backend has no trained prefixes)."""
    encoder = FakeEncoder(dimension=16)

    as_query   = await encoder.encode([TICKET_TEXT], "query")
    as_passage = await encoder.encode([TICKET_TEXT], "passage")
    as_sts     = await encoder.encode([TICKET_TEXT], "sts")

    assert as_query == as_passage == as_sts


async def test_encoder_reports_the_fake_model_name() -> None:
    """Encoder identity → "fake", so a collection built from these vectors is recognisable."""
    encoder = FakeEncoder(dimension=16)

    assert encoder.model_name == "fake"


def test_encoder_reports_its_dimension() -> None:
    """Encoder exposes the width it was built with → the factory can check it against config."""
    assert FakeEncoder(dimension=768).dimension == 768
