"""
Description:
Uruchomienie grafu na żywym, płatnym modelu w testach `llm_live`: graf złożony z węzłów
właściwych tą samą funkcją co w fabryce grafów, z atrapą anonimizatora i podanymi narzędziami.
Korzystają z niego test okablowania grafów (`tests/integration/api_agent_graphs/`) i scenariusze
ewaluacyjne (`tests/evaluation/`).

| co                     | do czego                                                          |
|------------------------|-------------------------------------------------------------------|
| `run_live_graph()`     | jedna sprawa: stan przykładowy grafu z podanym wejściem i regułami |
| `live_state()`         | stan wejściowy takiej sprawy, bez modelu                          |
| `LiveCase`             | sprawa dla `run_live_cases()`: wejście, reguły klienta, narzędzia |
| `run_live_cases()`     | wiele spraw grafu naraz; sprawa odrzucona przez `respond` to `None` |
| `default_rules()`      | reguły klienta z zestawu domyślnego grafu, po sprawdzeniu wersji  |
| `remember_per_graph()` | pomiar grafu liczony raz na plik testów, razem z błędem            |

O czym pamiętać przy zmianach:

- Konfigurację modelu podaje wołający, wziętą przez `live_generation_llm()` z `tests/conftest.py`.
  Ta funkcja odmawia, gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa, więc
  tu jej się nie omija.
- Anonimizator to atrapa, bo zgłoszenia w tych testach są zmyślone; atrapa oddaje tekst bez zmian.
- Limity wywołań narzędzi i limit tur pochodzą z konfiguracji, tak jak w fabryce grafów.
- Graf z regułami klienta bez podanych reguł dostaje reguły ze swojego stanu przykładowego, a nie
  zestaw domyślny, którego używa trasa. Scenariusz bramki podaje więc reguły zawsze, wzięte przez
  `default_rules()`.
"""

import asyncio
import dataclasses
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import TypeVar

from pydantic import BaseModel

from app.agent_graphs import run_graph
from app.agent_graphs.factory import build_real_graph
from app.agent_nodes.respond import RespondError
from app.agent_tools import AgentTool
from app.config import LLMSettings, Settings
from app.core_service.loader_dict_rules import get_rule_set
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import get_llm_client
from tests.helpers_agent_tools import fake_agent_tools

# Wynik pomiaru, który `remember_per_graph()` zapamiętuje: dowolny, byle jeden na graf.
Measured = TypeVar("Measured")


@dataclasses.dataclass(frozen=True)
class LiveCase:
    """Sprawa do przepuszczenia przez graf na żywym modelu: wejście, reguły klienta i narzędzia."""

    text:  str                                # wejście grafu, np. "ZGŁOSZENIE 90101…"
    rules: Sequence[str] | None = None        # reguły klienta; None — reguły z przykładu grafu
    tools: Sequence[AgentTool] | None = None  # narzędzia sprawy; None — `fake_agent_tools()`


async def run_live_graph(
    graph:      ModuleType,                   # np. <module app.agent_graphs.search>
    llm:        LLMSettings,                  # np. live_generation_llm(request.config)
    tools:      Sequence[AgentTool],          # np. fake_agent_tools()
    input_text: str | None = None,            # np. "ZGŁOSZENIE 90101…"; None — z przykładu
    rules:      Sequence[str] | None = None,  # np. ["Wiadomość nie prosi…"]; None — z przykładu
) -> BaseModel:
    """
    Description:
    Składa graf tą samą funkcją, której używa fabryka grafów (`build_real_graph()`) — z limitami
    wywołań i limitem tur z konfiguracji — i przepuszcza przez niego wejście na prawdziwym
    modelu: przykładowy stan grafu (`example_state()`) albo ten stan z podmienionym wejściem
    i regułami klienta. Reszta stanu zostaje jak w przykładzie.

    Example args:
        graph=<module app.agent_graphs.search>
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)
        tools=fake_agent_tools()
        input_text=None
        rules=None

    Example result:
        SearchState(sources=[SourceRef(item_id="90001", …), …], iterations=4,
                    usage=LLMUsage(calls=4, cost_usd=0.021, …), …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział w czasie albo oddał turę nie do użycia;
            także `RespondError`, gdy model mimo poprawki nie oddał poprawnej odpowiedzi
    """
    settings = Settings()

    compiled = build_real_graph(
        graph          = graph,
        llm            = get_llm_client(llm),
        anonymizer     = FakeAnonymizer(),
        tools          = tools,
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )

    return await run_graph(compiled, live_state(graph, input_text, rules))


def live_state(
    graph:      ModuleType,                   # np. <module app.agent_graphs.gate_reply>
    input_text: str | None = None,            # np. "Dzień dobry, …"; None — z przykładu
    rules:      Sequence[str] | None = None,  # np. ["Wiadomość nie prosi…"]; None — z przykładu
) -> BaseModel:
    """
    Description:
    Stan wejściowy sprawy: przykładowy stan grafu (`example_state()`) z podmienionym wejściem
    i regułami klienta, gdy je podano. Reszta stanu zostaje jak w przykładzie.

    Example args:
        graph=<module app.agent_graphs.gate_reply>
        input_text="Dzień dobry, prosimy Państwa…"
        rules=["Wiadomość nie prosi klienta o hasło ani login."]

    Example result:
        GateReplyState(input_text="Dzień dobry, prosimy Państwa…",
                       rules=["Wiadomość nie prosi klienta o hasło ani login."], …)
    """
    update: dict[str, object] = {}

    # --- własne wejście zamiast przykładowego ---
    if input_text is not None:
        update["input_text"] = input_text

    # --- własne reguły klienta zamiast przykładowych ---
    if rules is not None:
        update["rules"] = list(rules)

    state = graph.example_state().model_copy(update=update)

    return state


async def run_live_cases(
    graph: ModuleType,          # np. <module app.agent_graphs.gate_reply>
    llm:   LLMSettings,         # np. live_generation_llm(request.config)
    cases: Sequence[LiveCase],  # np. [LiveCase(text="Dzień dobry, prosimy…", rules=[…]), …]
) -> list[BaseModel | None]:
    """
    Description:
    Przepuszcza wszystkie sprawy grafu naraz, każdą na jej narzędziach (bez podanych — na
    atrapach wszystkich narzędzi), i oddaje stany końcowe w kolejności spraw. Sprawa, której
    odpowiedzi węzeł `respond` nie przyjął mimo poprawki, daje `None`: to wynik sprawy, który
    ocenia scenariusz. Inne błędy modelu (sieć, odmowa dostawcy) lecą dalej, bo to awaria
    przebiegu.

    Example args:
        graph=<module app.agent_graphs.gate_reply>
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        cases=[LiveCase(text="Dzień dobry, prosimy Państwa o przesłanie loginu…",
                        rules=["Wiadomość nie prosi…"])]

    Example result:
        [GateReplyState(output=Verdict(verdict="block", …), respond_retries=0, …), None]

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    finals = await asyncio.gather(*(_run_or_reject(graph, llm, case) for case in cases))

    return list(finals)


async def _run_or_reject(
    graph: ModuleType,   # np. <module app.agent_graphs.gate_reply>
    llm:   LLMSettings,  # np. live_generation_llm(request.config)
    case:  LiveCase,     # np. LiveCase(text="Dzień dobry, prosimy Państwa…", rules=[…])
) -> BaseModel | None:
    """
    Description:
    Przepuszcza jedną sprawę przez graf na jej narzędziach i oddaje stan końcowy, a `None`,
    gdy węzeł `respond` nie przyjął odpowiedzi mimo poprawki.

    Example args:
        graph=<module app.agent_graphs.gate_reply>
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        case=LiveCase(text="Dzień dobry, prosimy Państwa…", rules=["Wiadomość nie prosi…"])

    Example result:
        GateReplyState(output=Verdict(verdict="block", …), respond_retries=0, …)

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    tools = fake_agent_tools() if case.tools is None else case.tools

    try:
        return await run_live_graph(graph, llm, tools, case.text, case.rules)
    except RespondError:  # odpowiedź nie do przyjęcia: ocenia ją scenariusz, nie przebieg
        return None


def default_rules(
    graph:   str,         # np. "gate_reply"
    version: int | None,  # np. 1 — wersja zestawu, pod którą napisano scenariusz; None — bez reguł
) -> list[str] | None:
    """
    Description:
    Reguły klienta z zestawu domyślnego grafu (`get_rule_set()`), tego samego, który bierze
    trasa — po sprawdzeniu, że to wersja, pod którą napisano scenariusz. Scenariusz bez wersji
    dotyczy grafu bez reguł i dostaje `None`. Sprawdzenie stoi przed wołaniem modelu: sprawy
    napisane pod inne reguły nie mierzą nic, a kosztowałyby jak zwykle.

    Example args:
        graph="gate_reply"
        version=1

    Example result:
        ["Wiadomość nie prosi klienta o hasło ani login.", …]

    Raises:
        AssertionError: zestaw domyślny ma inną wersję niż scenariusz
    """
    # --- graf bez reguł klienta ---
    if version is None:
        return None

    rule_set = get_rule_set(graph)

    assert rule_set.version == version, (
        f"{graph}: scenariusz napisany pod reguły w wersji {version}, a zestaw domyślny ma "
        f"wersję {rule_set.version} — przejrzyj sprawy pod nowe reguły i podbij wersję w zestawie"
    )

    return list(rule_set.rules)


def remember_per_graph(
    measure: Callable[[str], Measured],  # np. lambda name: _measure(name, llm, …)
) -> Callable[[str], Measured]:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu woła pomiar raz i zapamiętuje wynik — razem z błędem,
    jeśli pomiar się nim skończył. Każdy kolejny test tego grafu dostaje ten sam wynik albo ten
    sam błąd, więc nieudany pomiar nie jest opłacany od nowa w każdym teście.

    Example args:
        measure=lambda name: _measure(name, llm, live_usage, gate_report)

    Example result:
        funkcja: run("gate_reply") -> [GateOutcome(…), …] (za drugim razem bez wołania modelu)
    """
    done: dict[str, Measured | Exception] = {}

    def run(
        name: str,  # np. "gate_reply"
    ) -> Measured:
        # --- pierwsza prośba o ten graf: pomiar na żywym modelu ---
        if name not in done:
            try:
                done[name] = measure(name)
            except Exception as error:  # noqa: BLE001 — zapamiętany i zgłoszony każdemu testowi
                done[name] = error

        # --- pomiar skończył się błędem: każdy test tego grafu dostaje ten sam błąd ---
        if isinstance(done[name], Exception):
            raise done[name]

        return done[name]

    return run
