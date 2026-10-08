"""
Description:
Narzędzia agenta dla testów węzłów, grafów i tras.

| helper                                     | co oddaje                                          |
|--------------------------------------------|----------------------------------------------------|
| `fake_agent_tools()`                       | atrapy wszystkich narzędzi agenta                  |
| `fake_agent_tools_without_material()`      | te same atrapy, ale wyszukiwania nic nie znajdują  |
| `find_tickets_vector_with_dead_embedder()` | narzędzie właściwe, którego embedder nie odpowiada |

O czym pamiętać przy zmianach:

- Atrapa narzędzia (`Fake…Tool`) zawsze odpowiada. Stan, którego nie umie odtworzyć — padniętą
  zależność — daje narzędzie właściwe z zepsutym transportem, a nie podklasa atrapy: błąd ma
  zgłosić prawdziwy klient zależności, swoim typem, a klasa narzędzia zdefiniowana w teście
  trafiłaby do testu kontraktu narzędzi, który sam znajduje wszystkie klasy narzędzi w procesie.
"""

import httpx

from app.agent_tools import AgentTool
from app.agent_tools.code.quote_code.fake import FakeQuoteCodeTool
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.db_qdrant import QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests.helpers_transport import raising, with_transport

# Wymiar wektora kolekcji; do Qdranta i tak nic nie dochodzi, bo wcześniej pada embedder.
VECTOR_SIZE = 4


def fake_agent_tools() -> list[AgentTool]:
    """
    Description:
    Atrapy wszystkich narzędzi agenta, w kolejności z `TOOL_NAMES` grafów — te same, które
    model widziałby w produkcie, tylko na zmyślonym materiale. Świeże na każde wywołanie, bo
    zapisują zapytania, o które je pytano.

    Example args:
        (brak)

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeReadTicketsCardTool(), …]
    """
    tools: list[AgentTool] = [
        FakeFindTicketsVectorTool(),
        FakeFindTicketsTextTool(),
        FakeReadTicketsCardTool(),
        FakeReadTicketsThreadTool(),
        FakeListDocsTool(),
        FakeFindDocsVectorTool(),
        FakeFindDocsTextTool(),
        FakeReadDocsTool(),
        FakeQuoteCodeTool(),
    ]

    return tools


def fake_agent_tools_without_material() -> list[AgentTool]:
    """
    Description:
    Atrapy wszystkich narzędzi agenta, w których nic nie ma do znalezienia: wyszukiwania zgłoszeń
    i dokumentacji oddają puste listy, spis dokumentacji jest pusty, a cytowanie kodu nie zna
    żadnego pliku. Odczyty zgłoszeń i dokumentacji zostają takie same, ale model nie ma skąd
    wziąć identyfikatora, więc sprawa kończy się bez źródeł. Kolejność jak w `fake_agent_tools()`.

    Cytowanie kodu jest puste, bo przykład ścieżki w opisie `quote_code` to plik z wbudowanego
    zestawu atrapy: model mógłby go zacytować na ślepo i dostać źródło.

    Example args:
        (brak)

    Example result:
        [FakeFindTicketsVectorTool(tickets=[]), FakeFindTicketsTextTool(tickets=[]), …]
    """
    tools: list[AgentTool] = [
        FakeFindTicketsVectorTool(tickets=[]),
        FakeFindTicketsTextTool(tickets=[]),
        FakeReadTicketsCardTool(),
        FakeReadTicketsThreadTool(),
        FakeListDocsTool(sections=[]),
        FakeFindDocsVectorTool(found=[]),
        FakeFindDocsTextTool(matched=[]),
        FakeReadDocsTool(),
        FakeQuoteCodeTool(files={}),
    ]

    return tools


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
