import math

import pytest

from embedder_app.encoding import deterministic_vector

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"

# Recorded output of the current algorithm. Not a magic constant to be "fixed" when it fails:
# a changed value means indexed vectors no longer match freshly computed ones, which silently
# breaks every recall assertion built on this backend. Update it only alongside a deliberate
# change to deterministic_vector — and re-index whatever was built with the old one.
GOLDEN_VECTOR_DIM_4 = [
    -0.6217898978404582,
    -0.715272348583971,
    -0.16192790798410245,
    -0.2748493094599569,
]


def test_same_text_yields_identical_vector() -> None:
    """Same text embedded twice → identical vectors (the property the whole fake exists for)."""
    assert deterministic_vector(TICKET_TEXT, 8) == deterministic_vector(TICKET_TEXT, 8)


def test_mapping_is_stable_across_code_changes() -> None:
    """Known text and dimension → the recorded vector (guards the text→vector mapping itself)."""
    assert deterministic_vector(TICKET_TEXT, 4) == GOLDEN_VECTOR_DIM_4


def test_different_texts_yield_different_vectors() -> None:
    """Two unrelated texts → different vectors (a constant answer would fake every recall test)."""
    assert deterministic_vector(TICKET_TEXT, 8) != deterministic_vector(OTHER_TICKET_TEXT, 8)


def test_vector_has_requested_dimension() -> None:
    """Dimension argument → vector of exactly that length (it is a contract with the collection)."""
    assert len(deterministic_vector(TICKET_TEXT, 768)) == 768


def test_vector_is_unit_length() -> None:
    """Any text → L2 norm of 1, so cosine scores land in the range thresholds are tuned against."""
    vector = deterministic_vector(TICKET_TEXT, 768)

    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


def test_texts_differing_only_by_diacritics_are_distinct() -> None:
    """Text with Polish diacritics vs its ASCII spelling → different vectors (UTF-8 bytes hash)."""
    assert deterministic_vector("błąd drukarki", 8) != deterministic_vector("blad drukarki", 8)
