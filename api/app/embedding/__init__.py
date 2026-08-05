"""
Description:
How `api` reaches the `embedder` service. Import from here
(`from app.embedding import EmbeddingClient`) rather than from the submodules — the split between
client and errors is an internal detail, while this surface is what domain code is allowed to know
about turning text into vectors.

No factory here, unlike `app.llm`: there is exactly one way to reach the embedder (HTTP), and
which MODEL answers is the embedder's own configuration, not ours. What varies is a URL, and a
URL is an argument.
"""

from app.embedding.client import EmbeddingClient
from app.embedding.errors import EmbeddingConfigError, EmbeddingError

__all__ = [
    "EmbeddingClient",
    "EmbeddingConfigError",
    "EmbeddingError",
]
