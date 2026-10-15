"""
Description:
Każdy graf na prawdziwym modelu generującym z konfiguracji (`LLM_GENERATION_*`), złożony
z węzłów właściwych — `agent`, `run_tools` i `respond` — z promptem i opisami narzędzi produktu.
Narzędzia to atrapy na zmyślonym materiale, a anonimizator to atrapa (zgłoszenia są zmyślone).

Testy sprawdzają okablowanie, którego nie pokaże atrapa modelu: czy dostawca przyjmuje narzędzie
odpowiedzi każdego grafu, czy model nim odpowiada i czy ta odpowiedź przechodzi walidację do
wyniku grafu, a w grafach z pętlą — czy dostawca przyjmuje rozmowę rosnącą z tury na turę.
Jakości odpowiedzi nie sprawdzają: to pomiary grafów (CLAUDE.md -> „Plan", p. 21–28). Sprawy
przeprowadza `tests/_helpers/live/measure.py`.

KOSZTUJE: jeden przebieg pliku to jedna sprawa na graf, czyli osiem spraw — pięć po jednej turze
i trzy w pętli po kilka tur z dwunastoma narzędziami — oraz dwie sprawy `suggest_solution`:
na narzędziach, które nic nie znajdują, i ze zgłoszeniem, którego komunikat stoi tylko w kodzie
aplikacji (razem rząd kilkunastu centów na mocnym modelu). Sprawa każdego grafu liczy się raz,
dopiero gdy potrzebuje jej test, i jest wspólna dla jego testów — więc `-k gate_close` uruchamia
i opłaca tylko ten jeden graf.
"""

from types import ModuleType

import pytest
from pydantic import BaseModel

from app.agent_graphs import suggest_solution
from app.config import Settings
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from tests._helpers.graphs import graph_modules, graph_name, output_types
from tests._helpers.live import (
    PROVIDER_SELFHOSTED,
    LiveRunOf,
    LiveUsageReport,
    live_generation_llm,
    measure_example_case,
    measure_solution_with_message_in_code,
    measure_solution_without_material,
    remember_per_graph,
)

pytestmark = pytest.mark.llm_live

# Pakiety wszystkich grafów i te z nich, które mają pętlę agent ⇄ run_tools.
GRAPHS      = graph_modules()
LOOP_GRAPHS = [graph for graph in GRAPHS if graph.TOOL_NAMES]


@pytest.fixture(scope="module")
def live_run(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> LiveRunOf:
    """
    Description:
    Oddaje funkcję, która dla nazwy grafu zwraca stan końcowy jego sprawy przykładowej na
    prawdziwym modelu (`measure_example_case()`). Sprawa liczy się przy pierwszym teście, który
    o nią poprosi, i jest zapamiętana na cały plik — razem z błędem, jeśli się nim skończyła
    (`remember_per_graph()`). Konfigurację bierze przez `live_generation_llm()`, które odmawia,
    gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        funkcja: live_run("search") -> SearchState(sources=[…], iterations=4, …)
    """
    llm = live_generation_llm(request.config)

    return remember_per_graph(lambda name: measure_example_case(name, llm, live_usage))


@pytest.fixture(scope="module")
def solution_without_material(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Stan końcowy sprawy `suggest_solution` na prawdziwym modelu, w której narzędzia nic nie
    znajdują (`measure_solution_without_material()`). Osobna sprawa obok tej z `live_run`,
    liczona dopiero, gdy poprosi o nią test.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SuggestSolutionState(sources=[], output=ProposalNotes(internal_notes="Szukałem…"), …)
    """
    return measure_solution_without_material(live_generation_llm(request.config), live_usage)


@pytest.fixture(scope="module")
def solution_with_message_in_code(
    request:    pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
    live_usage: LiveUsageReport,        # wstrzykiwane przez pytest; raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Stan końcowy sprawy `suggest_solution` na prawdziwym modelu, w której zgłoszenie niesie
    komunikat z ekranu, a materiał jest tylko w kodzie aplikacji
    (`measure_solution_with_message_in_code()`). Para do sprawy bez materiału — różni je
    zgłoszenie z komunikatem — liczona dopiero, gdy poprosi o nią test.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SuggestSolutionState(sources=[SourceRef(source="code", …)], output=Proposal(…), …)
    """
    return measure_solution_with_message_in_code(live_generation_llm(request.config), live_usage)


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
def test_the_model_answers_with_the_respond_tool_and_the_answer_is_accepted(
    graph:    ModuleType,
    live_run: LiveRunOf,
) -> None:
    """Sprawdza, czy w każdym grafie prawdziwy model kończy sprawę wywołaniem narzędzia odpowiedzi
    tego grafu, zanim wyczerpie limit tur, a węzeł odpowiedzi przyjmuje tę odpowiedź — najwyżej
    po jednej poprawce — i zapisuje wynik w typie grafu: werdykt, kartę, tekst albo propozycję.
    Wariant wymagający źródeł, w którym model niczego nie odczytał, kończy z samymi uwagami dla
    wdrożeniowca.

    Wyłapuje graf, którego narzędzia odpowiedzi dostawca nie przyjmuje albo w którego pola model
    nie trafia: na atrapie modelu taki graf działa, a na prawdziwym każda sprawa kończy się
    błędem."""
    final       = live_run(graph_name(graph))
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert final.log[-1].node == "respond"
    assert final.iterations   <= Settings().agent_max_iterations
    assert [call.name for call in model_turns[-1].tool_calls] == [graph.RESPOND_TOOL_NAME]

    # --- wariant wymagający źródeł bez źródeł: zostają same uwagi, i to jest poprawny przebieg ---
    if getattr(graph, "REQUIRES_HITS", False) and not final.sources:
        assert isinstance(final.output, ProposalNotes)

        return

    assert isinstance(final.output, output_types(graph)[0])


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
def test_every_model_turn_calls_a_tool(graph: ModuleType, live_run: LiveRunOf) -> None:
    """Sprawdza, czy w każdym grafie każda tura prawdziwego modelu jest wywołaniem narzędzia,
    a nie samym tekstem.

    Wyłapuje model, który odpowiada tekstem zamiast narzędziem: taka tura kosztuje poprawkę albo
    całą sprawę, więc wymuszenie wywołania narzędzia u dostawcy musi działać."""
    final       = live_run(graph_name(graph))
    model_turns = [message for message in final.messages if message.role == "assistant"]

    assert model_turns
    assert all(turn.tool_calls for turn in model_turns)


@pytest.mark.parametrize("graph", GRAPHS, ids=graph_name)
def test_the_cost_of_the_run_is_the_sum_of_its_turns(
    graph:    ModuleType,
    live_run: LiveRunOf,
) -> None:
    """Sprawdza, czy zużycie całej sprawy zgadza się z jej przebiegiem w każdym grafie: tyle
    wywołań modelu, ile było tur, policzone tokeny wejścia i wyjścia oraz koszt większy od zera,
    a przy modelu self-hosted równy zeru.

    Wyłapuje koszt sprawy, w którym giną tury — także tura poprawki: wołający widziałby
    w odpowiedzi ułamek tego, co sprawa naprawdę kosztowała."""
    usage        = live_run(graph_name(graph)).usage
    input_tokens = usage.prompt_tokens + usage.cache_write_tokens + usage.cache_read_tokens

    assert usage.calls             == live_run(graph_name(graph)).iterations
    assert input_tokens            > 0
    assert usage.completion_tokens > 0

    if Settings().llm_generation().provider.strip().lower() == PROVIDER_SELFHOSTED:
        assert usage.cost_usd == 0.0
    else:
        assert usage.cost_usd > 0


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
def test_the_model_reads_what_it_found(graph: ModuleType, live_run: LiveRunOf) -> None:
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy sprawa kończy się listą źródeł: model
    nie tylko wyszukał materiał, ale też odczytał choć jedno zgłoszenie albo sekcję dokumentacji,
    albo zacytował fragment kodu jako przyczynę.

    Wyłapuje pętlę, w której model szuka i od razu kończy albo w której wyniki naszych narzędzi
    do niego nie docierają: odpowiedź wróciłaby wtedy bez żadnego źródła."""
    final = live_run(graph_name(graph))

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
