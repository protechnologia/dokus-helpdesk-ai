from collections.abc import Iterator

import langsmith.utils
import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

import app.graph  # noqa: F401 — sam import pakietu grafów ma wyłączyć LangSmith


class State(BaseModel):
    """Stan sondy: czy LangSmith śledzi przebieg, widziane z wnętrza węzła."""

    traced: bool | None = None


async def probe(
    state: State,  # np. State()
) -> dict[str, bool]:
    """
    Description:
    Węzeł-sonda: zapisuje, czy w trakcie przebiegu tracing jest włączony.

    Example args:
        state=State()

    Example result:
        {"traced": False}
    """
    return {"traced": bool(langsmith.utils.tracing_is_enabled())}


@pytest.fixture
def tracing_requested(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Description:
    Ustawia ENV, które bez blokady włączyłoby tracing. Endpoint jest lokalny i martwy, żeby zepsuta
    blokada skończyła się nieudanym połączeniem, a nie wysyłką.

    Example args:
        monkeypatch=<fixture pytest>

    Example result:
        None — ENV ustawione na czas testu
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2-test")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "http://127.0.0.1:9")

    # langsmith zapamiętuje odczytane zmienne (lru_cache), więc bez czyszczenia czytałby stare.
    langsmith.utils.get_env_var.cache_clear()
    yield
    langsmith.utils.get_env_var.cache_clear()


async def test_a_graph_runs_untraced_when_env_asks_for_tracing(tracing_requested: None) -> None:
    """LANGSMITH_TRACING=true → wewnątrz węzła tracing wyłączony: import `app.graph` blokuje go
    globalnie, więc stan sprzed anonimizacji nie wychodzi do chmury."""
    assert langsmith.utils.get_env_var("TRACING") == "true", "bez blokady ENV włączyłoby tracing"

    graph = StateGraph(State)
    graph.add_node("probe", probe)
    graph.add_edge(START, "probe")
    graph.add_edge("probe", END)

    result = await graph.compile().ainvoke(State())

    assert result["traced"] is False
