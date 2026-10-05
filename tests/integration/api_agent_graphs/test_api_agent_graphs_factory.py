import importlib
import pkgutil
from collections.abc import Iterator
from types import ModuleType

import pytest

import app.agent_graphs
from app.agent_graphs import factory, gate_close, run_graph, search
from app.agent_graphs.factory import (
    build_function_graph,
    close_process_agent_tools,
    process_agent_tools,
)
from app.agent_nodes.agent import tool_call_turn
from app.config import Settings
from app.engine_anonymization import AnonymizationConfigError, FakeAnonymizer
from app.engine_llm import ChatMessage, FakeLLMClient
from tests.helpers_agent_tools import fake_agent_tools

# Fabryka grafów: co konfiguracja robi z grafem, o który prosi trasa. Przy atrapie modelu ma
# wyjść atrapa grafu, przy prawdziwym dostawcy graf z węzłów właściwych — a dopóki nie ma
# prawdziwego anonimizatora, odmowa. Zależności prawdziwej drogi (anonimizator, klient modelu,
# narzędzia na bazach) testy podmieniają na atrapy, bo sprawdzają składanie, nie usługi.

GRAPHS = [
    importlib.import_module(f"app.agent_graphs.{module.name}")
    for module in pkgutil.iter_modules(app.agent_graphs.__path__)
    if module.ispkg
]

# Tura modelu z samym tekstem: przyjmuje ją tylko atrapa węzła odpowiedzi.
PLAIN_TEXT = ChatMessage(role="assistant", content="Odpowiadam zwykłym tekstem.")


def name_of(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> str:
    """
    Description:
    Nazwa grafu = nazwa jego katalogu.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        "gate_close"
    """
    return graph.__name__.split(".")[-1]


@pytest.fixture(autouse=True)
def no_tools_left_between_tests() -> Iterator[None]:
    """
    Description:
    Czyści narzędzia zapamiętane przez fabrykę przed testem i po nim: są zapamiętywane na cały
    proces, więc bez tego jeden test dostawałby narzędzia zbudowane w innym.

    Example args:
        (brak)

    Example result:
        None — `process_agent_tools()` w teście buduje narzędzia od nowa
    """
    process_agent_tools.cache_clear()

    yield

    process_agent_tools.cache_clear()


def use_a_real_provider(
    monkeypatch: pytest.MonkeyPatch,  # np. fixture pytest
) -> None:
    """
    Description:
    Ustawia konfigurację na prawdziwego dostawcę modelu generującego, z kluczem i modelem — tak,
    żeby jedyną przeszkodą w budowie grafu mógł być anonimizator.

    Example args:
        monkeypatch=<fixture pytest>

    Example result:
        None — `Settings()` oddaje dostawcę `openai` z kluczem i modelem
    """
    monkeypatch.setenv("LLM_GENERATION_PROVIDER", "openai")
    monkeypatch.setenv("LLM_GENERATION_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_GENERATION_MODEL", "gpt-5.4-mini")


def use_fake_dependencies(
    monkeypatch: pytest.MonkeyPatch,  # np. fixture pytest
    llm:         FakeLLMClient,       # np. FakeLLMClient(turns=[…])
) -> None:
    """
    Description:
    Podmienia to, z czego fabryka składa graf na prawdziwym modelu: anonimizator, klienta modelu
    i narzędzia na bazach. Sama fabryka i węzły zostają prawdziwe.

    Example args:
        monkeypatch=<fixture pytest>
        llm=FakeLLMClient(turns=[tool_call_turn("respond_search", {})])

    Example result:
        None — fabryka buduje graf na atrapach zależności
    """
    monkeypatch.setattr(factory, "build_anonymizer", lambda settings: FakeAnonymizer())
    monkeypatch.setattr(factory, "get_llm_client", lambda settings: llm)
    monkeypatch.setattr(factory, "build_agent_tools", lambda settings: fake_agent_tools())


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
async def test_with_the_fake_model_the_factory_gives_a_fake_graph(graph: ModuleType) -> None:
    """Sprawdza, czy przy atrapie modelu fabryka oddaje dla każdego grafu przebieg, który dochodzi
    do wyniku bez żadnej zależności: bez klienta modelu, anonimizatora i narzędzi na bazach.

    Wyłapuje fabrykę, która przy domyślnej konfiguracji sięga po prawdziwe zależności: świeżo
    postawiony stack nie odpowiadałby na żadne żądanie, a zwykły test trasy wołałby usługi."""
    final = await run_graph(build_function_graph(graph), graph.example_state())

    assert final.output is not None
    assert process_agent_tools.cache_info().currsize == 0


async def test_the_provider_name_is_read_regardless_of_case_and_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy dostawca wpisany jako „ Fake " jest traktowany jak atrapa, tak samo jak
    czyta go fabryka klienta modelu.

    Wyłapuje dwie fabryki, które tę samą wartość czytają różnie: klient modelu byłby atrapą,
    a fabryka grafów szłaby drogą prawdziwego dostawcy i kończyła odmową anonimizatora."""
    monkeypatch.setenv("LLM_GENERATION_PROVIDER", " Fake ")

    final = await run_graph(build_function_graph(gate_close), gate_close.example_state())

    assert final.output is not None


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_a_real_model_without_a_real_anonymizer_is_refused(
    graph:       ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy przy prawdziwym dostawcy modelu fabryka odmawia zbudowania każdego grafu
    błędem konfiguracji anonimizatora i nie buduje przy tym narzędzi.

    Wyłapuje graf, który ruszyłby na prawdziwym modelu z atrapą anonimizatora: surowe zgłoszenie
    z danymi klienta wyszłoby do zewnętrznego dostawcy."""
    use_a_real_provider(monkeypatch)

    with pytest.raises(AnonymizationConfigError):
        build_function_graph(graph)

    assert process_agent_tools.cache_info().currsize == 0


async def test_a_real_model_gets_a_graph_of_real_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy przy prawdziwym dostawcy fabryka składa graf wyszukiwania z węzłów
    właściwych: model dostaje prompt grafu i narzędzia z limitem z konfiguracji (tu 7 dla
    `read_docs`), a odpowiedź zwykłym tekstem wraca do poprawki, czego atrapa węzła odpowiedzi
    nie robi.

    Wyłapuje fabrykę, która przy prawdziwym modelu dalej oddaje atrapę grafu albo gubi limity:
    model liczyłby tury, a wołający dostawałby stałą odpowiedź atrapy."""
    llm = FakeLLMClient(turns=[PLAIN_TEXT, tool_call_turn(search.RESPOND_TOOL_NAME, {})])

    use_a_real_provider(monkeypatch)
    use_fake_dependencies(monkeypatch, llm)
    monkeypatch.setenv("AGENT_MAX_CALLS_READ_DOCS", "7")

    final     = await run_graph(build_function_graph(search), search.example_state())
    first     = llm.turn_calls[0]
    read_docs = next(tool for tool in first.tools if tool.name == "read_docs")

    assert final.output          == search.SearchDone()
    assert final.respond_retries == 1
    assert first.system          == search.system_prompt()
    assert [tool.name for tool in first.tools] == [*search.TOOL_NAMES, search.RESPOND_TOOL_NAME]
    assert "Limit wywołań w jednej sprawie: 7." in read_docs.description


async def test_a_graph_without_tools_builds_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy przy prawdziwym dostawcy graf bez narzędzi wiedzy, tu bramka zamknięcia,
    powstaje i działa bez zbudowania narzędzi na bazach.

    Wyłapuje bramkę, która przy starcie sięga do embeddera, Qdranta albo Postgresa: ma działać
    także wtedy, gdy indeks jest pusty, a te usługi leżą."""
    answer = tool_call_turn(gate_close.RESPOND_TOOL_NAME, {"verdict": "pass"})

    use_a_real_provider(monkeypatch)
    use_fake_dependencies(monkeypatch, FakeLLMClient(turns=[answer]))

    final = await run_graph(build_function_graph(gate_close), gate_close.example_state())

    assert final.output.verdict == "pass"
    assert process_agent_tools.cache_info().currsize == 0


def test_the_tools_are_built_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy narzędzia na bazach powstają raz: drugie żądanie dostaje te same obiekty,
    a budowa jest wołana jeden raz.

    Wyłapuje narzędzia budowane na każde żądanie: każde zakładałoby nową pulę połączeń
    z Postgresem, a ten ładuje słownik w każdej sesji, więc każde wyszukanie czekałoby na to
    od nowa."""
    built: list[Settings] = []

    def build(settings: Settings) -> list:
        built.append(settings)

        return fake_agent_tools()

    monkeypatch.setattr(factory, "build_agent_tools", build)

    first  = process_agent_tools()
    second = process_agent_tools()

    assert len(built) == 1
    assert all(one is other for one, other in zip(first, second, strict=True))


async def test_closing_closes_every_tool_and_forgets_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zamknięcie przy wyłączaniu aplikacji zamyka każde zbudowane narzędzie
    i zapomina je, więc następne użycie zbudowałoby nowe.

    Wyłapuje narzędzie pominięte przy zamykaniu (jego połączenia zostałyby otwarte) oraz
    zapamiętane narzędzia z zamkniętymi połączeniami, które dostałoby następne żądanie."""
    tools  = fake_agent_tools()
    closed: list[str] = []

    for tool in tools:

        async def aclose(name: str = tool.name) -> None:
            closed.append(name)

        monkeypatch.setattr(tool, "aclose", aclose)

    monkeypatch.setattr(factory, "build_agent_tools", lambda settings: tools)

    process_agent_tools()
    await close_process_agent_tools()

    assert closed == [tool.name for tool in tools]
    assert process_agent_tools.cache_info().currsize == 0


async def test_closing_without_built_tools_builds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zamknięcie aplikacji, w której żadne żądanie nie potrzebowało narzędzi na
    bazach, niczego nie buduje.

    Wyłapuje zamykanie, które najpierw buduje narzędzia, żeby je zamknąć: przy atrapie modelu
    wyłączenie aplikacji kończyłoby się błędem konfiguracji bazy, której nikt nie używał."""
    def build(settings: Settings) -> list:
        raise AssertionError("narzędzia nie powinny powstać przy zamykaniu")

    monkeypatch.setattr(factory, "build_agent_tools", build)

    await close_process_agent_tools()

    assert process_agent_tools.cache_info().currsize == 0
