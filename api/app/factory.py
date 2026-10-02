import logging
from collections.abc import Callable
from functools import lru_cache
from types import ModuleType

from langgraph.graph.state import CompiledStateGraph

from app.config import Settings
from app.embedding import EmbeddingClient
from app.llm import get_llm_client
from app.retrieval import QdrantClient
from app.service.parser_ticket_parsed import TicketParser
from app.service.rag_searcher import RagSearcher

logger = logging.getLogger(__name__)

# Budowa grafu funkcji z jego modułu (np. `app.graph.gate_close`) — to, o co trasy proszą fabrykę.
GraphBuilder = Callable[[ModuleType], CompiledStateGraph]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Description:
    Konfiguracja aplikacji, czytana raz. `Settings()` czyta środowisko i `.env` przy każdej
    budowie, a handler robiący to na każde żądanie płaciłby I/O za coś, co nie zmienia się
    w trakcie życia procesu.

    Example args:
        (brak)

    Example result:
        Settings(qdrant_url="http://qdrant:6333", rag_top_k=5, …)
    """
    return Settings()


def build_searcher(
    settings: Settings,  # np. Settings(qdrant_collection="tickets", rag_top_k=5)
) -> RagSearcher:
    """
    Description:
    Buduje serwis wyszukiwania z konfiguracji — dziś dla `helpdesk rag search`; `POST /search`
    idzie już przez graf `search`. Klienci transportowi zostają wewnątrz serwisu: sprzątający woła
    `searcher.aclose()` i nie musi wiedzieć, z czego serwis jest zbudowany.

    Example args:
        settings=Settings(qdrant_url="http://qdrant:6333", rag_top_k=5)

    Example result:
        RagSearcher odpytujący kolekcję `tickets` z top_k=5

    Raises:
        LLMConfigError: źle skonfigurowany dostawca LLM
        RetrievalConfigError: pusty `QDRANT_URL` albo `QDRANT_COLLECTION`
    """
    searcher = RagSearcher(
        parser   = TicketParser(llm=get_llm_client(settings)),
        embedder = EmbeddingClient(
            base_url = settings.embedding_base_url,
            timeout  = settings.embedding_timeout_seconds,
        ),
        qdrant = QdrantClient(
            base_url   = settings.qdrant_url,
            collection = settings.qdrant_collection,
            timeout    = settings.qdrant_timeout_seconds,
        ),
        top_k     = settings.rag_top_k,
        score_min = settings.rag_score_min,
    )

    # Sama konfiguracja — bez sekretów i adresów poza nazwą kolekcji.
    logger.info(
        "searcher ready collection=%s top_k=%d score_min=%.3f",
        settings.qdrant_collection,
        settings.rag_top_k,
        settings.rag_score_min,
    )

    return searcher


def build_function_graph(
    graph: ModuleType,  # np. app.graph.gate_close
) -> CompiledStateGraph:
    """
    Description:
    Buduje graf funkcji, o który prosi trasa. DZIŚ ZAWSZE ATRAPĘ, niezależnie od `LLM_PROVIDER`:
    właściwych węzłów jeszcze nie ma (p. 9–11), a atrapa nie wysyła niczego poza proces — więc
    nie ma czego chronić odmową, a odmowa położyłaby trasy na stacku dev z prawdziwym modelem.
    Wybór po konfiguracji (klient LLM, anonimizator, narzędzia) wchodzi tu razem z p. 9.

    Atrapa jest jednorazowa (`FakeAgent` ma zaplanowane tury), dlatego graf powstaje na każde
    żądanie, a nie raz na proces.

    Example args:
        graph=app.graph.gate_close

    Example result:
        CompiledStateGraph złożony z atrap węzłów
    """
    return graph.build_fake_graph()


def get_graph_builder() -> GraphBuilder:
    """
    Description:
    Zależność FastAPI: skąd trasy biorą grafy. Osobna od `build_function_graph`, żeby test mógł ją
    podmienić (`app.dependency_overrides`) i wstawić atrapę z wybranym wynikiem.

    Example args:
        (brak)

    Example result:
        build_function_graph
    """
    return build_function_graph
