"""
Description:
Fabryka grafów: z pakietu grafu (na przykład `app.agent_graphs.gate_close`) robi gotowy
przebieg, o który proszą trasy. To tu konfiguracja rozstrzyga, na czym graf stoi.

| `LLM_GENERATION_PROVIDER` | co oddaje fabryka                                               |
|---------------------------|-----------------------------------------------------------------|
| `fake` (domyślnie)        | atrapę grafu (`build_fake_graph()`): stałe odpowiedzi, nic nie  |
|                           | wychodzi z procesu                                              |
| prawdziwy dostawca        | graf z węzłów właściwych (`build_real_graph()`): anonimizator,  |
|                           | model i narzędzia z konfiguracji                                |

Co się dzieje po drodze przy prawdziwym dostawcy:

1. Anonimizator powstaje pierwszy (`build_anonymizer()`). Dopóki jest tylko atrapa, która tekstu
   nie zmienia, budowa kończy się tu błędem konfiguracji i nic więcej nie powstaje.
2. Klient modelu generującego powstaje z kompletu `LLM_GENERATION_*`.
3. Graf z narzędziami wiedzy dostaje narzędzia na prawdziwych bazach — te same w każdym
   żądaniu (`process_agent_tools()`) — oraz limity ich wywołań i limit tur modelu.
4. `build_real_graph()` składa z tego węzły: `anonymize`, `agent`, w grafie z narzędziami
   `run_tools`, i `respond` z pakietu grafu.

O czym pamiętać przy zmianach:

- Dostawca `fake` to atrapa CAŁEGO grafu, nie węzły właściwe na atrapie modelu: atrapa modelu
  bez scenariusza odpowiada samym tekstem, więc węzeł `respond` odrzucałby każdą sprawę.
- Graf powstaje na każde żądanie: atrapa jest jednorazowa (`FakeAgentNode` ma zaplanowane tury),
  a węzły właściwe są tanie. Narzędzia na prawdziwych bazach żyją tyle, co proces, bo trzymają
  pulę połączeń; zamyka je `close_process_agent_tools()` przy wyłączaniu aplikacji.
- `build_real_graph()` nie czyta konfiguracji — dostaje gotowe zależności. Dzięki temu ten sam
  kod składa graf dla tras, dla testów na atrapach zależności i dla testów na żywym modelu.
- Ten moduł nie jest eksportowany z `app.agent_graphs`: czyta konfigurację i pociąga klientów,
  a tamten `__init__` importuje każdy graf.
"""

import functools
from collections.abc import Callable, Mapping, Sequence
from types import ModuleType

from langgraph.graph.state import CompiledStateGraph

from app.agent_nodes.agent import AgentNode
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools import AgentTool
from app.agent_tools.factory import build_agent_tools
from app.config import Settings
from app.engine_anonymization import Anonymizer, build_anonymizer
from app.engine_llm import LLMClient, get_llm_client
from app.engine_llm.factory import PROVIDER_FAKE

# Budowa grafu funkcji z jego modułu (np. `app.agent_graphs.gate_close`) — to, o co trasy proszą
# fabrykę.
GraphBuilder = Callable[[ModuleType], CompiledStateGraph]


def build_real_graph(
    graph:          ModuleType,           # np. app.agent_graphs.search
    llm:            LLMClient,            # np. get_llm_client(Settings().llm_generation())
    anonymizer:     Anonymizer,           # np. build_anonymizer(Settings())
    tools:          Sequence[AgentTool],  # wszystkie dostępne narzędzia; graf bierze dozwolone
    limits:         Mapping[str, int],    # np. Settings().tool_call_limits()
    max_iterations: int,                  # np. 20 — limit tur modelu z `AGENT_MAX_ITERATIONS`
) -> CompiledStateGraph:
    """
    Description:
    Składa graf funkcji z węzłów właściwych na podanych zależnościach. Prompt, narzędzia, które
    model może widzieć, i węzeł odpowiedzi bierze z pakietu grafu, więc działa tak samo dla
    każdego grafu — także takiego, którego jeszcze nie ma.

    Z podanych narzędzi graf dostaje te ze swojej listy `TOOL_NAMES`, w jej kolejności; pozostałe
    są pomijane. Graf bez narzędzi wiedzy nie ma węzła `run_tools` ani limitu tur.

    Example args:
        graph=app.agent_graphs.search
        llm=FakeLLMClient(turns=[tool_call_turn("respond_search", {})])
        anonymizer=FakeAnonymizer()
        tools=[FakeFindTicketsVectorTool(), FakeReadTicketsCardTool(), …]
        limits={"find_tickets_vector": 5, "read_tickets_card": 5, …}
        max_iterations=20

    Example result:
        CompiledStateGraph: anonymize → agent ⇄ run_tools → respond, wszystkie węzły właściwe

    Raises:
        ValueError: graf z narzędziami wiedzy nie dostał żadnego ze swoich narzędzi albo
            narzędzie nie ma limitu wywołań
    """
    # --- narzędzia tego grafu, w kolejności jego listy ---
    available = {tool.name: tool for tool in tools}
    allowed   = [available[name] for name in graph.TOOL_NAMES if name in available]

    anonymize = AnonymizeNode(anonymizer)
    agent     = AgentNode(
        llm           = llm,
        system_prompt = graph.system_prompt(),
        user_prompt   = graph.user_prompt,
        tools         = graph.model_tools(allowed, limits),
    )
    respond   = graph.respond_node()

    # --- graf bez narzędzi wiedzy: jedna tura modelu i odpowiedź ---
    if not graph.TOOL_NAMES:
        return graph.build_graph(anonymize=anonymize, agent=agent, respond=respond)

    # --- graf z narzędziami: pętla z wykonaniem narzędzi i limitem tur ---
    compiled = graph.build_graph(
        anonymize      = anonymize,
        agent          = agent,
        run_tools      = RunToolsNode(allowed, limits),
        respond        = respond,
        max_iterations = max_iterations,
    )

    return compiled


@functools.cache
def process_agent_tools() -> tuple[AgentTool, ...]:
    """
    Description:
    Narzędzia agenta na prawdziwych bazach, zbudowane raz na proces. Kolejne żądania dostają te
    same obiekty, więc pula połączeń Postgresa i połączenia HTTP żyją między żądaniami.

    Example args:
        (brak)

    Example result:
        (FindTicketsVectorTool(…), FindTicketsTextTool(…), …, ReadDocsTool(…))

    Raises:
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
        DbPostgresConfigError: brak hasła albo pusta nazwa bazy
    """
    return tuple(build_agent_tools(Settings()))


async def close_process_agent_tools() -> None:
    """
    Description:
    Zamyka narzędzia zbudowane przez `process_agent_tools()` i zapomina je, więc następne użycie
    zbuduje nowe. Gdy żadnych nie zbudowano — przy atrapie modelu to zwykły przypadek — nie robi
    nic. Woła to aplikacja przy wyłączaniu.

    Example args:
        (brak)

    Example result:
        None
    """
    # --- nic nie powstało: nie ma czego zamykać ---
    if not process_agent_tools.cache_info().currsize:
        return

    for tool in process_agent_tools():
        await tool.aclose()

    process_agent_tools.cache_clear()


def _build_fake_graph(
    graph:    ModuleType,  # np. app.agent_graphs.search
    settings: Settings,    # np. Settings()
) -> CompiledStateGraph:
    """
    Description:
    Buduje atrapę grafu. Graf z narzędziami dostaje z konfiguracji limity ich wywołań i limit tur
    modelu — atrapy egzekwują je tą samą regułą co węzły właściwe.

    Example args:
        graph=app.agent_graphs.search
        settings=Settings()

    Example result:
        CompiledStateGraph złożony z atrap węzłów
    """
    # --- graf bez narzędzi wiedzy: jedna tura, nie ma czego limitować ---
    if not graph.TOOL_NAMES:
        return graph.build_fake_graph()

    # --- graf z narzędziami: limity z konfiguracji ---
    return graph.build_fake_graph(
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )


def build_function_graph(
    graph: ModuleType,  # np. app.agent_graphs.gate_close
) -> CompiledStateGraph:
    """
    Description:
    Buduje graf funkcji, o który prosi trasa. Przy atrapie modelu generującego oddaje atrapę
    grafu, przy prawdziwym dostawcy — graf z węzłów właściwych na anonimizatorze, modelu
    i narzędziach z konfiguracji.

    Do czasu prawdziwego anonimizatora (p. 19) druga droga kończy się błędem konfiguracji:
    atrapa anonimizatora tekstu nie zmienia, więc `build_anonymizer()` odmawia jej przy każdym
    dostawcy innym niż `fake` i surowe zgłoszenie nie wychodzi z procesu.

    Example args:
        graph=app.agent_graphs.gate_close

    Example result:
        CompiledStateGraph: atrapa grafu albo graf z węzłów właściwych

    Raises:
        AnonymizationConfigError: prawdziwy model generujący bez prawdziwego anonimizatora
        LLMConfigError: nieznany dostawca albo brak klucza czy modelu
        EmbeddingConfigError, DbQdrantConfigError, DbPostgresConfigError: zła konfiguracja
            zależności narzędzi
    """
    settings = Settings()

    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje nie mogą wybierać drogi — tak
    # samo czyta ją fabryka klienta modelu.
    provider = settings.llm_generation_provider.strip().lower()

    # --- atrapa modelu: cały graf z atrap, nic nie wychodzi z procesu ---
    if provider == PROVIDER_FAKE:
        return _build_fake_graph(graph, settings)

    # --- prawdziwy model: anonimizator pierwszy, żeby bez niego nie powstało nic więcej ---
    anonymizer = build_anonymizer(settings)
    llm        = get_llm_client(settings.llm_generation())

    compiled = build_real_graph(
        graph          = graph,
        llm            = llm,
        anonymizer     = anonymizer,
        tools          = process_agent_tools() if graph.TOOL_NAMES else (),
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )

    return compiled


def get_graph_builder() -> GraphBuilder:
    """
    Description:
    Zależność FastAPI: skąd trasy biorą grafy. Osobna od `build_function_graph`, żeby test mógł ją
    podmienić (`app.dependency_overrides`) i wstawić własny graf.

    Example args:
        (brak)

    Example result:
        build_function_graph
    """
    return build_function_graph
