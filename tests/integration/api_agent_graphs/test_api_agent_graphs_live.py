import asyncio
import importlib
import pkgutil
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import get_args

import pytest
from pydantic import BaseModel

import app.agent_graphs
from app.agent_graphs import run_graph, suggest_solution
from app.agent_graphs.factory import build_real_graph
from app.agent_tools import AgentTool
from app.config import LLMSettings, Settings
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import get_llm_client
from tests.conftest import live_generation_llm
from tests.helpers_agent_tools import (
    fake_agent_tools,
    fake_agent_tools_with_code_only,
    fake_agent_tools_without_material,
)
from tests.helpers_live_usage import LiveUsageReport

pytestmark = pytest.mark.llm_live

# Każdy graf na prawdziwym modelu generującym z konfiguracji (`LLM_GENERATION_*`), złożony
# z węzłów właściwych — `agent`, `run_tools` i `respond` — z promptem i opisami narzędzi produktu.
# Narzędzia to atrapy na zmyślonym materiale, a anonimizator to atrapa (zgłoszenia są zmyślone).
#
# Testy sprawdzają okablowanie, którego nie pokaże atrapa modelu: czy dostawca przyjmuje narzędzie
# odpowiedzi każdego grafu, czy model nim odpowiada i czy ta odpowiedź przechodzi walidację do
# wyniku grafu, a w grafach z pętlą — czy dostawca przyjmuje rozmowę rosnącą z tury na turę.
# Jakości odpowiedzi nie sprawdzają: to pomiary grafów (CLAUDE.md -> „Plan", p. 21–28).
#
# KOSZTUJE: jeden przebieg pliku to jedna sprawa na graf, czyli osiem spraw — pięć po jednej turze
# i trzy w pętli po kilka tur z dwunastoma narzędziami — oraz dwie sprawy `suggest_solution`:
# na narzędziach, które nic nie znajdują, i ze zgłoszeniem, którego komunikat stoi tylko w kodzie
# aplikacji (razem rząd kilkunastu centów na mocnym modelu). Sprawa
# każdego grafu liczy się raz, dopiero gdy potrzebuje jej test, i jest wspólna dla jego testów —
# więc `-k gate_close` uruchamia i opłaca tylko ten jeden graf.

GRAPHS = [
    importlib.import_module(f"app.agent_graphs.{module.name}")
    for module in pkgutil.iter_modules(app.agent_graphs.__path__)
    if module.ispkg
]

# Grafy z pętlą agent ⇄ run_tools.
LOOP_GRAPHS = [graph for graph in GRAPHS if graph.TOOL_NAMES]

# Dostawca self-hosted: nasz sprzęt nie nalicza tokenów, więc koszt sprawy to zero.
PROVIDER_SELFHOSTED = "ollama"

# Sprawa jednego grafu przeprowadzona na prawdziwym modelu: z grafu robi stan końcowy.
LiveRun = Callable[[ModuleType], BaseModel]

# Zmyślone zgłoszenie z komunikatem z ekranu. Ten komunikat stoi w zmyślonym kodzie atrap
# (`agent_tools/code/fake_code.py`), a nie ma go w żadnym zgłoszeniu ani instrukcji.
TICKET_WITH_MESSAGE = (
    "Od rana przy rejestracji pisma przychodzącego wyskakuje komunikat "
    "„Brak sekwencji numeracji dla roku 2026\". Wczoraj rejestracja działała bez problemu."
)


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


def output_type(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> type[BaseModel]:
    """
    Description:
    Typ wyniku grafu, odczytany z pola `output` jego stanu.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        Verdict
    """
    annotation = graph.STATE.model_fields["output"].annotation
    found      = [arg for arg in get_args(annotation) if arg is not type(None)]

    return found[0]


async def _run_the_graph(
    graph:  ModuleType,           # np. <module app.agent_graphs.search>
    llm:    LLMSettings,          # np. Settings().llm_generation()
    tools:  Sequence[AgentTool],  # np. fake_agent_tools()
    ticket: str | None = None,    # np. TICKET_WITH_MESSAGE; None to przykładowe zgłoszenie grafu
) -> BaseModel:
    """
    Description:
    Składa graf tą samą funkcją, której używa fabryka grafów (`build_real_graph()`) — z limitami
    wywołań i limitem tur z konfiguracji — i przepuszcza przez niego zgłoszenie na prawdziwym
    modelu: przykładowe zgłoszenie tego grafu albo podane w `ticket`. To jedyne miejsce w pliku,
    które woła model.

    Example args:
        graph=<module app.agent_graphs.search>
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)
        tools=fake_agent_tools()
        ticket=None

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

    state = graph.example_state()

    # --- własne zgłoszenie zamiast przykładowego: reszta stanu zostaje jak w przykładzie ---
    if ticket is not None:
        state = state.model_copy(update={"input_text": ticket})

    return await run_graph(compiled, state)


@pytest.fixture(scope="module")
def live_run(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> LiveRun:
    """
    Description:
    Oddaje funkcję, która dla grafu zwraca stan końcowy jego sprawy na prawdziwym modelu
    (`_run_the_graph()`). Sprawa liczy się przy pierwszym teście, który o nią poprosi, i jest
    zapamiętana na cały plik — razem z błędem, jeśli się nim skończyła, żeby nieudana sprawa nie
    była opłacana od nowa w każdym teście tego grafu. Konfigurację bierze przez
    `live_generation_llm()`, które odmawia, gdy testy wybrano bez jawnego `llm_live` albo gdy
    modelem jest atrapa. Zużycie i przebieg każdej udanej sprawy zgłasza do raportu przebiegu;
    sprawa zakończona błędem nie oddaje stanu, więc jej zużycia w raporcie nie ma.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: live_run(search) -> SearchState(sources=[…], iterations=4, …)
    """
    llm  = live_generation_llm(request.config)
    done: dict[str, BaseModel | Exception] = {}

    def run(
        graph: ModuleType,  # np. <module app.agent_graphs.search>
    ) -> BaseModel:
        name = name_of(graph)

        # --- pierwsza prośba o ten graf: jedna sprawa na prawdziwym modelu ---
        if name not in done:
            try:
                done[name] = asyncio.run(_run_the_graph(graph, llm, fake_agent_tools()))
            except Exception as error:  # noqa: BLE001 — zapamiętany i zgłoszony każdemu testowi
                done[name] = error
            else:
                final = done[name]
                live_usage.record(f"graf {name}", final.usage, final.log, final.messages)

        # --- sprawa skończyła się błędem: każdy test tego grafu dostaje ten sam błąd ---
        if isinstance(done[name], Exception):
            raise done[name]

        return done[name]

    return run


@pytest.fixture(scope="module")
def solution_without_material(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Stan końcowy sprawy `suggest_solution` na prawdziwym modelu, w której narzędzia nic nie
    znajdują (`fake_agent_tools_without_material()`). Osobna sprawa obok tej z `live_run`, liczona
    dopiero, gdy poprosi o nią test. Konfigurację bierze przez `live_generation_llm()`, tak jak
    `live_run`.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SuggestSolutionState(sources=[], output=ProposalNotes(internal_notes="Szukałem…"), …)
    """
    llm   = live_generation_llm(request.config)
    tools = fake_agent_tools_without_material()
    final = asyncio.run(_run_the_graph(suggest_solution, llm, tools))

    live_usage.record(
        "graf suggest_solution bez materiału", final.usage, final.log, final.messages,
    )

    return final


@pytest.fixture(scope="module")
def solution_with_message_in_code(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Stan końcowy sprawy `suggest_solution` na prawdziwym modelu, w której zgłoszenie niesie
    komunikat z ekranu (`TICKET_WITH_MESSAGE`), a materiał jest tylko w kodzie aplikacji
    (`fake_agent_tools_with_code_only()`): zgłoszenia i instrukcje nic nie znajdują. Para do
    sprawy bez materiału — różni je zgłoszenie z komunikatem — liczona dopiero, gdy poprosi
    o nią test.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SuggestSolutionState(sources=[SourceRef(source="code", …)], output=Proposal(…), …)
    """
    llm   = live_generation_llm(request.config)
    tools = fake_agent_tools_with_code_only()
    final = asyncio.run(_run_the_graph(suggest_solution, llm, tools, TICKET_WITH_MESSAGE))

    live_usage.record(
        "graf suggest_solution: komunikat tylko w kodzie", final.usage, final.log, final.messages,
    )

    return final


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_model_answers_with_the_respond_tool_and_the_answer_is_accepted(
    graph:    ModuleType,
    live_run: LiveRun,
) -> None:
    """Sprawdza, czy w każdym grafie prawdziwy model kończy sprawę wywołaniem narzędzia odpowiedzi
    tego grafu, zanim wyczerpie limit tur, a węzeł odpowiedzi przyjmuje tę odpowiedź — najwyżej
    po jednej poprawce — i zapisuje wynik w typie grafu: werdykt, kartę, tekst albo propozycję.
    Wariant wymagający źródeł, w którym model niczego nie odczytał, kończy z samymi uwagami dla
    wdrożeniowca.

    Wyłapuje graf, którego narzędzia odpowiedzi dostawca nie przyjmuje albo w którego pola model
    nie trafia: na atrapie modelu taki graf działa, a na prawdziwym każda sprawa kończy się
    błędem."""
    final       = live_run(graph)
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert final.log[-1].node == "respond"
    assert final.iterations   <= Settings().agent_max_iterations
    assert [call.name for call in model_turns[-1].tool_calls] == [graph.RESPOND_TOOL_NAME]

    # --- wariant wymagający źródeł bez źródeł: zostają same uwagi, i to jest poprawny przebieg ---
    if getattr(graph, "REQUIRES_HITS", False) and not final.sources:
        assert isinstance(final.output, ProposalNotes)

        return

    assert isinstance(final.output, output_type(graph))


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_every_model_turn_calls_a_tool(graph: ModuleType, live_run: LiveRun) -> None:
    """Sprawdza, czy w każdym grafie każda tura prawdziwego modelu jest wywołaniem narzędzia,
    a nie samym tekstem.

    Wyłapuje model, który odpowiada tekstem zamiast narzędziem: taka tura kosztuje poprawkę albo
    całą sprawę, więc wymuszenie wywołania narzędzia u dostawcy musi działać."""
    final       = live_run(graph)
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert model_turns
    assert all(turn.tool_calls for turn in model_turns)


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_cost_of_the_run_is_the_sum_of_its_turns(graph: ModuleType, live_run: LiveRun) -> None:
    """Sprawdza, czy zużycie całej sprawy zgadza się z jej przebiegiem w każdym grafie: tyle
    wywołań modelu, ile było tur, policzone tokeny wejścia i wyjścia oraz koszt większy od zera,
    a przy modelu self-hosted równy zeru.

    Wyłapuje koszt sprawy, w którym giną tury — także tura poprawki: wołający widziałby
    w odpowiedzi ułamek tego, co sprawa naprawdę kosztowała."""
    usage        = live_run(graph).usage
    input_tokens = usage.prompt_tokens + usage.cache_write_tokens + usage.cache_read_tokens

    assert usage.calls             == live_run(graph).iterations
    assert input_tokens            > 0
    assert usage.completion_tokens > 0

    if Settings().llm_generation().provider.strip().lower() == PROVIDER_SELFHOSTED:
        assert usage.cost_usd == 0.0
    else:
        assert usage.cost_usd > 0


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=name_of)
def test_the_model_reads_what_it_found(graph: ModuleType, live_run: LiveRun) -> None:
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy sprawa kończy się listą źródeł: model
    nie tylko wyszukał materiał, ale też odczytał choć jedno zgłoszenie albo sekcję dokumentacji,
    albo zacytował fragment kodu jako przyczynę.

    Wyłapuje pętlę, w której model szuka i od razu kończy albo w której wyniki naszych narzędzi
    do niego nie docierają: odpowiedź wróciłaby wtedy bez żadnego źródła."""
    final = live_run(graph)

    assert final.sources
    assert {ref.source for ref in final.sources} <= {"tickets", "docs", "code"}


def test_suggest_solution_without_material_ends_with_notes_only(
    solution_without_material: BaseModel,
) -> None:
    """Sprawdza, czy w wariancie z rozwiązaniem, w którym narzędzia nic nie znajdują, prawdziwy
    model kończy sprawę wywołaniem narzędzia odpowiedzi, a węzeł odpowiedzi przyjmuje je najwyżej
    po jednej poprawce. Lista źródeł jest pusta, a wynikiem są same uwagi dla wdrożeniowca, bez
    treści dla klienta. Treści uwag test nie ocenia.

    Wyłapuje model, który po pustym wyszukaniu odpowiada zwykłym tekstem. Węzeł odpowiedzi czyta
    odpowiedź także w sprawie bez źródeł, więc taki model dostaje poprawkę, a za drugim razem
    sprawa kończy się błędem 503 zamiast odpowiedzią „nie mam z czego zaproponować". Grozi to
    zwłaszcza przy modelach, którym nie wymuszamy wywołania narzędzia."""
    final       = solution_without_material
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert final.sources == []
    assert [call.name for call in model_turns[-1].tool_calls] == [
        suggest_solution.RESPOND_TOOL_NAME,
    ]
    assert isinstance(final.output, ProposalNotes)


def test_suggest_solution_with_a_message_only_in_the_code_ends_cleanly(
    solution_with_message_in_code: BaseModel,
) -> None:
    """Sprawdza, czy sprawa, w której zgłoszenie niesie komunikat z ekranu, a materiał jest tylko
    w kodzie aplikacji, kończy się na prawdziwym modelu wywołaniem narzędzia odpowiedzi. Jedynym
    możliwym źródłem jest kod: gdy model zacytował fragment jako przyczynę, wynikiem jest
    propozycja, a gdy nie, same uwagi dla wdrożeniowca. Czy model w ogóle sięga po szukanie
    w kodzie, test nie rozstrzyga: to widać w raporcie zużycia po przebiegu, a oczekiwanie
    z progiem należy do scenariuszy ewaluacyjnych (p. 59).

    Wyłapuje sprawę, w której wyniki narzędzi kodu psują rozmowę z dostawcą albo w której
    propozycja powstaje bez żadnego źródła: przy komunikacie, którego nie tłumaczy żadne
    zgłoszenie, klient dostałby rozwiązanie wzięte znikąd."""
    final       = solution_with_message_in_code
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert [call.name for call in model_turns[-1].tool_calls] == [
        suggest_solution.RESPOND_TOOL_NAME,
    ]
    assert {ref.source for ref in final.sources} <= {"code"}
    assert isinstance(final.output, Proposal if final.sources else ProposalNotes)
