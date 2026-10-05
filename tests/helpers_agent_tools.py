"""
Description:
Narzędzia agenta w stanie, którego atrapy z produkcji nie umieją odtworzyć — do testów węzła
`run_tools`, grafów i tras. Atrapa narzędzia (`Fake…Tool`) zawsze odpowiada; tu jest narzędzie
właściwe, którego zależność nie działa.

Dlaczego narzędzie właściwe z zepsutym transportem, a nie podklasa atrapy: błąd ma zgłosić
prawdziwy klient zależności, swoim typem — a klasa narzędzia zdefiniowana w teście trafiłaby do
testu kontraktu narzędzi, który sam znajduje wszystkie klasy narzędzi w procesie.
"""

import httpx

from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool
from app.db_qdrant import QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests.helpers_transport import raising, with_transport

# Wymiar wektora kolekcji; do Qdranta i tak nic nie dochodzi, bo wcześniej pada embedder.
VECTOR_SIZE = 4


def find_tickets_vector_with_dead_embedder() -> FindTicketsVectorTool:
    """
    Description:
    Narzędzie `find_tickets_vector`, którego embedder nie odpowiada: każde wyszukanie kończy się
    `EmbeddingError`, tak jak przy padniętej usłudze `embedder`.

    Example args:
        (brak)

    Example result:
        FindTicketsVectorTool, którego `find()` zgłasza EmbeddingError
    """
    embedder = with_transport(
        EmbeddingClient(base_url="http://embedder:8000"),
        raising(httpx.ConnectError("connection refused")),
    )
    qdrant = QdrantClient(base_url="http://qdrant:6333")

    tool = FindTicketsVectorTool(
        embedder  = embedder,
        tickets   = TicketsCollection(qdrant, "tickets", VECTOR_SIZE),
        top_k     = 5,
        score_min = 0.48,
    )

    return tool
