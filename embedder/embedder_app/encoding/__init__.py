"""
Description:
Backend-agnostic access to vector encoding. Import from here
(`from embedder_app.encoding import Encoder`) rather than from the submodules — the split between
interface, fake and factory is an internal detail, while this surface is what the HTTP layer is
allowed to know about a model.
"""

from embedder_app.encoding.base import Encoder
from embedder_app.encoding.errors import EncoderConfigError, EncoderError
from embedder_app.encoding.factory import build_encoder, get_encoder
from embedder_app.encoding.fake import FakeEncoder, deterministic_vector
from embedder_app.encoding.sentence_transformer import (
    MODE_PREFIXES,
    SentenceTransformerEncoder,
)

__all__ = [
    "MODE_PREFIXES",
    "Encoder",
    "EncoderConfigError",
    "EncoderError",
    "FakeEncoder",
    "SentenceTransformerEncoder",
    "build_encoder",
    "deterministic_vector",
    "get_encoder",
]
