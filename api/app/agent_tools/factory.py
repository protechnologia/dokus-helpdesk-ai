"""
Description:
Buduje narzędzia agenta na prawdziwych zależnościach, z konfiguracji: jeden klient embeddera,
jeden Qdranta i jeden Postgresa, a na nich osiem narzędzi, oraz paczka kodu aplikacji na dysku
z czterema: jedno w niej szuka programem ripgrep, drugie spisuje jej katalogi, trzecie czyta jej
pliki, czwarte ją cytuje.

| narzędzie             | na czym stoi                                         |
|-----------------------|------------------------------------------------------|
| `find_tickets_vector` | embedder i kolekcja zgłoszeń (`QDRANT_COLLECTION`)   |
| `find_tickets_text`   | tabela zgłoszeń w Postgresie                         |
| `read_tickets_card`   | kolekcja zgłoszeń i słownik rozstrzygnięć            |
| `read_tickets_thread` | tabela zgłoszeń w Postgresie                         |
| `list_docs`           | tabela dokumentacji w Postgresie                     |
| `find_docs_vector`    | embedder i kolekcja `QDRANT_DOCS_COLLECTION`         |
| `find_docs_text`      | tabela dokumentacji w Postgresie                     |
| `read_docs`           | tabela dokumentacji w Postgresie                     |
| `find_code_text`      | paczka kodu aplikacji i program ripgrep              |
| `list_code_files`     | paczka kodu aplikacji na dysku (`CODE_PACKAGE_DIR`)  |
| `read_code_file`      | paczka kodu aplikacji na dysku (`CODE_PACKAGE_DIR`)  |
| `quote_code`          | paczka kodu aplikacji na dysku (`CODE_PACKAGE_DIR`)  |

Do czego:
Fabryka grafów (`agent_graphs/factory.py`) bierze stąd narzędzia, gdy model generujący nie jest
atrapą, i wybiera z nich te, które dany graf dopuszcza. Atrapy narzędzi nie powstają tutaj:
buduje je ten, kto ich potrzebuje — testy i atrapy grafów.

O czym pamiętać przy zmianach:

- Narzędzia buduje się raz na proces, nie na żądanie. Postgres ładuje słownik w każdej sesji
  (około 0,6 s), więc klient musi trzymać pulę połączeń między żądaniami.
- Budowa nie łączy się z niczym i nie dotyka dysku — połączenia powstają przy pierwszym użyciu
  narzędzia, a brak paczki kodu albo ripgrepa wychodzi przy pierwszym użyciu narzędzia kodu.
- Kolejność listy jest kolejnością `TOOL_NAMES` grafów. Model dostaje definicje narzędzi w tej
  kolejności w każdej turze, a stały początek żądania to warunek cache promptu.
- Kto zbudował narzędzia, ten je zamyka: `aclose()` każdego z nich. Klienci są wspólni, więc
  zamykają się po kilka razy; powtórne zamknięcie nic nie robi.
- Powstają wszystkie. Czy instancja bez dokumentacji ma pomijać jej narzędzia, rozstrzyga
  p. 15 (CLAUDE.md -> „Plan").
"""

from app.agent_tools.base import AgentTool
from app.agent_tools.code.find_code_text import FindCodeTextTool
from app.agent_tools.code.list_code_files import ListCodeFilesTool
from app.agent_tools.code.quote_code import QuoteCodeTool
from app.agent_tools.code.read_code_file import ReadCodeFileTool
from app.agent_tools.docs.find_docs_text import FindDocsTextTool
from app.agent_tools.docs.find_docs_vector import FindDocsVectorTool
from app.agent_tools.docs.list_docs import ListDocsTool
from app.agent_tools.docs.read_docs import ReadDocsTool
from app.agent_tools.tickets.find_tickets_text import FindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card import ReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread import ReadTicketsThreadTool
from app.config import Settings
from app.core_service.loader_code_package import CodePackage
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.db_postgres import DocsTable, PostgresClient, TicketsTable
from app.db_qdrant import DocsCollection, QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from app.engine_process.ripgrep import RipgrepClient


def build_agent_tools(
    settings: Settings,  # np. Settings()
) -> list[AgentTool]:
    """
    Description:
    Buduje wszystkie narzędzia agenta na klientach i paczce kodu z konfiguracji, w kolejności
    `TOOL_NAMES` grafów. Nie łączy się z niczym — połączenia powstają przy pierwszym użyciu.

    Example args:
        settings=Settings()

    Example result:
        [FindTicketsVectorTool(…), FindTicketsTextTool(…), ReadTicketsCardTool(…),
         ReadTicketsThreadTool(…), ListDocsTool(…), FindDocsVectorTool(…), FindDocsTextTool(…),
         ReadDocsTool(…), FindCodeTextTool(…), ListCodeFilesTool(…), ReadCodeFileTool(…),
         QuoteCodeTool(…)]

    Raises:
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
        DbPostgresConfigError: brak hasła albo pusta nazwa bazy
    """
    # --- klienci: po jednym na usługę, wspólni dla narzędzi ---
    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    postgres = PostgresClient(
        host     = settings.postgres_host,
        port     = settings.postgres_port,
        database = settings.postgres_db,
        user     = settings.postgres_user,
        password = settings.postgres_password,
        timeout  = settings.postgres_timeout_seconds,
    )

    # --- to, na czym stoją narzędzia: karty i fragmenty w Qdrancie, wątki i sekcje w Postgresie ---
    tickets_cards = TicketsCollection(
        client      = qdrant,
        name        = settings.qdrant_collection,
        vector_size = settings.embedding_vector_size,
    )
    docs_fragments = DocsCollection(
        client      = qdrant,
        name        = settings.qdrant_docs_collection,
        vector_size = settings.embedding_vector_size,
    )
    tickets_threads = TicketsTable(postgres)
    docs_sections   = DocsTable(postgres)

    # --- kod aplikacji: folder paczki, bez bazy; szuka w nim program uruchamiany procesem ---
    code    = CodePackage(settings.code_package_dir)
    ripgrep = RipgrepClient(timeout=settings.code_search_timeout_seconds)

    tools: list[AgentTool] = [
        FindTicketsVectorTool(
            embedder  = embedder,
            tickets   = tickets_cards,
            top_k     = settings.rag_top_k,
            score_min = settings.rag_score_min,
        ),
        FindTicketsTextTool(tickets=tickets_threads, limit=settings.rag_top_k),
        ReadTicketsCardTool(tickets=tickets_cards, resolution=get_resolution_classes()),
        ReadTicketsThreadTool(tickets=tickets_threads),
        ListDocsTool(docs=docs_sections),
        FindDocsVectorTool(
            embedder  = embedder,
            docs      = docs_fragments,
            top_k     = settings.rag_top_k,
            score_min = settings.rag_docs_score_min,
        ),
        FindDocsTextTool(docs=docs_sections, limit=settings.rag_top_k),
        ReadDocsTool(docs=docs_sections),
        FindCodeTextTool(package=code, ripgrep=ripgrep),
        ListCodeFilesTool(package=code),
        ReadCodeFileTool(package=code),
        QuoteCodeTool(package=code),
    ]

    return tools
