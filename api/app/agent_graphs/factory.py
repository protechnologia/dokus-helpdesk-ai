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
    Buduje graf funkcji, o który prosi trasa. DZIŚ ZAWSZE ATRAPĘ, niezależnie od `LLM_PROVIDER`:
    właściwych węzłów jeszcze nie ma (p. 9–11), a atrapa nie wysyła niczego poza proces — więc
    nie ma czego chronić odmową, a odmowa położyłaby trasy na stacku dev z prawdziwym modelem.
    Wybór po konfiguracji (klient LLM, anonimizator, narzędzia) wchodzi tu razem z p. 9.

    Atrapa jest jednorazowa (`FakeAgentNode` ma zaplanowane tury), dlatego graf powstaje na każde
    żądanie, a nie raz na proces.

    Graf z narzędziami dostaje limity ich wywołań z konfiguracji (`AGENT_MAX_CALLS_*`) — atrapa
    `run_tools` egzekwuje je tak samo, jak będzie to robił węzeł właściwy.

    Example args:
        graph=app.agent_graphs.gate_close

    Example result:
        CompiledStateGraph złożony z atrap węzłów
    """
    # --- graf bez narzędzi wiedzy: nie ma czego limitować ---
    if not graph.TOOL_NAMES:
        return graph.build_fake_graph()

    # --- graf z narzędziami: limity wywołań z konfiguracji ---
    limits = Settings().tool_call_limits()

    return graph.build_fake_graph(limits=limits)


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
