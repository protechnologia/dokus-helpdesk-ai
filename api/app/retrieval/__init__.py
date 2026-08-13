"""
Description:
How `api` reaches the Qdrant index. Import from here (`from app.retrieval import QdrantClient`)
rather than from the submodules — the split between client, errors and the transport model is an
internal detail, while this surface is what domain code may know about storing and finding
records.

No factory here, like `app.embedding` and unlike `app.llm`: there is one way to reach the index
(HTTP to one service), so what varies is a URL, and a URL is an argument. The day another vector
database becomes a real option, a factory belongs in this package — and nothing outside it should
have to change.

`TicketPoint` lives here rather than in `model/` on purpose: it describes what crosses the wire to
one particular service, so swapping that service touches this directory alone (CLAUDE.md ->
"Warstwy kodu": what talks to an external service gets its own package, transport models included).
"""

from app.retrieval.client import QdrantClient
from app.retrieval.errors import RetrievalConfigError, RetrievalError
from app.retrieval.model_point import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    TicketPoint,
    point_id_for,
)

__all__ = [
    "VECTOR_PROBLEM",
    "VECTOR_STS",
    "QdrantClient",
    "RetrievalConfigError",
    "RetrievalError",
    "TicketPoint",
    "point_id_for",
]
