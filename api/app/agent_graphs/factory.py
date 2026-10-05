from collections.abc import Callable
from types import ModuleType

from langgraph.graph.state import CompiledStateGraph

from app.config import Settings

# Budowa grafu funkcji z jego modułu (np. `app.agent_graphs.gate_close`) — to, o co trasy proszą
# fabrykę.
GraphBuilder = Callable[[ModuleType], CompiledStateGraph]


def build_function_graph(
    graph: ModuleType,  # np. app.agent_graphs.gate_close
) -> CompiledStateGraph:
    """
    Description:
    Buduje graf funkcji, o który prosi trasa. DZIŚ ZAWSZE ATRAPĘ, także przy prawdziwym modelu:
    właściwe są węzły `agent` i `run_tools`, a `respond` to jeszcze atrapa (p. 11). Graf
    z prawdziwym modelem i tą atrapą płaciłby za tury, których wynik i tak zastępuje atrapa —
    a atrapa grafu nie wysyła niczego poza proces, więc nie ma czego chronić odmową, a odmowa
    położyłaby trasy na stacku dev z prawdziwym modelem. Wybór po konfiguracji (klient LLM,
    anonimizator, narzędzia) wchodzi tu z p. 11.

    Atrapa jest jednorazowa (`FakeAgentNode` ma zaplanowane tury), dlatego graf powstaje na każde
    żądanie, a nie raz na proces.

    Graf z narzędziami dostaje z konfiguracji limity ich wywołań (`AGENT_MAX_CALLS_*`) i limit
    tur modelu (`AGENT_MAX_ITERATIONS`) — atrapy egzekwują je tą samą regułą co węzły właściwe.

    Example args:
        graph=app.agent_graphs.gate_close

    Example result:
        CompiledStateGraph złożony z atrap węzłów
    """
    # --- graf bez narzędzi wiedzy: jedna tura, nie ma czego limitować ---
    if not graph.TOOL_NAMES:
        return graph.build_fake_graph()

    # --- graf z narzędziami: limity z konfiguracji ---
    settings = Settings()

    return graph.build_fake_graph(
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )


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
