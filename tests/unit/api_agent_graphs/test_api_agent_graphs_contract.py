import importlib
import pkgutil
import re
from types import ModuleType
from typing import get_args, get_type_hints

import pytest
from pydantic import BaseModel

import app.agent_graphs
from app.agent_graphs import merge_sources
from app.agent_tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.agent_tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.agent_tools.docs.list_docs.fake import FakeListDocsTool
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.config import Settings
from app.engine_anonymization import AnonymizedText


def all_graphs() -> list[ModuleType]:
    """
    Description:
    Zbiera pakiety grafów z `app/agent_graphs/` — także tych, których jeszcze nie ma. Nowy graf to
    nowy katalog, więc test ma go znaleźć sam.

    Example args:
        (brak)

    Example result:
        [<module app.agent_graphs.gate_close>, <module app.agent_graphs.gate_reply>, …]
    """
    graphs = [
        importlib.import_module(f"app.agent_graphs.{module.name}")
        for module in pkgutil.iter_modules(app.agent_graphs.__path__)
        if module.ispkg
    ]

    return graphs


GRAPHS         = all_graphs()
RESPOND_GRAPHS = [graph for graph in GRAPHS if hasattr(graph, "RESPOND_TOOL_NAME")]

# Każde narzędzie agenta, jakie dziś istnieje, w kolejności z `TOOL_NAMES` grafów — test wybiera
# z nich dozwolone dla grafu.
AGENT_TOOLS = [
    FakeFindTicketsVectorTool(),
    FakeFindTicketsTextTool(),
    FakeReadTicketsCardTool(),
    FakeReadTicketsThreadTool(),
    FakeListDocsTool(),
    FakeFindDocsVectorTool(),
    FakeFindDocsTextTool(),
    FakeReadDocsTool(),
]

# Limity wywołań narzędzi, jakie daje konfiguracja domyślna.
LIMITS = Settings(_env_file=None).tool_call_limits()

# Znacznik zamiast tekstu po anonimizacji — gdy jest w prompcie, a tekstu surowego nie ma, prompt
# wziął treść z `anonymized`.
ANONYMIZED = "ZANONIMIZOWANE-7f3a"


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


def anonymized_state(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> BaseModel:
    """
    Description:
    Przykładowy stan grafu po anonimizacji, w którym tekst zanonimizowany to znacznik.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        GateCloseState(input_text="Nie przychodzą…", anonymized=AnonymizedText(text="ZANON…"), …)
    """
    state = graph.example_state().model_copy(update={"anonymized": AnonymizedText(text=ANONYMIZED)})

    return state


def filled_by(
    graph: ModuleType,  # np. <module app.agent_graphs.parse_ticket>
) -> tuple[str, ...]:
    """
    Description:
    Pola wyniku, których model nie podaje, bo wypełnia je graf — dziś tylko w `parse_ticket`.

    Example args:
        graph=<module app.agent_graphs.parse_ticket>

    Example result:
        ("ticket_id", "date", "resolution_vocabulary_version")
    """
    return getattr(graph, "FILLED_BY_GRAPH", ())


def allowed_tools(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> list:
    """
    Description:
    Atrapy narzędzi z listy dozwolonych dla grafu.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeListDocsTool(), …]
    """
    return [tool for tool in AGENT_TOOLS if tool.name in graph.TOOL_NAMES]


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_every_graph_exposes_the_same_api(graph: ModuleType) -> None:
    """Sprawdza, czy pakiet każdego grafu wystawia ten sam komplet: klasę stanu, listę narzędzi
    wiedzy, oba prompty, definicje narzędzi dla modelu, budowę przebiegu i jego atrapy oraz stan
    przykładowy.

    Wyłapuje graf, któremu czegoś z tego kompletu brakuje: trasy, CLI i węzeł `agent` sięgają po te
    rzeczy tak samo w każdym grafie, więc brak wyszedłby dopiero przy wywołaniu."""
    for attribute in (
        "STATE",             # klasa stanu grafu
        "TOOL_NAMES",        # narzędzia wiedzy dozwolone w grafie
        "system_prompt",     # prompt systemowy
        "user_prompt",       # tura użytkownika ze stanu
        "model_tools",       # definicje narzędzi dla modelu
        "build_graph",       # przebieg z gotowych węzłów
        "build_fake_graph",  # ten sam przebieg na atrapach
        "example_state",     # stan wejściowy do testów
    ):
        assert hasattr(graph, attribute), attribute


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
async def test_the_fake_graph_runs_from_anonymization_to_output(graph: ModuleType) -> None:
    """Sprawdza, czy atrapa każdego grafu, uruchomiona na stanie przykładowym, oddaje wynik w typie
    tego grafu, a jej przebieg zaczyna się od anonimizacji i kończy na odpowiedzi.

    Wyłapuje graf, który nie dochodzi do wyniku, oddaje wynik w cudzym typie albo nie zaczyna od
    anonimizacji, przez co surowe zgłoszenie mogłoby trafić do modelu."""
    state_type = type(graph.example_state())
    state      = state_type(**await graph.build_fake_graph().ainvoke(graph.example_state()))

    assert isinstance(state.output, output_type(graph))
    assert state.log[0].node  == "anonymize"
    assert state.log[-1].node == "respond"


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
async def test_the_fake_agent_answers_through_the_respond_tool(graph: ModuleType) -> None:
    """Sprawdza, czy w atrapie każdego grafu ostatnia tura modelu jest wywołaniem narzędzia
    odpowiedzi tego grafu, a jego argumenty to wynik grafu bez pól, które graf wypełnia sam.

    Wyłapuje atrapę, która odpowiada inaczej niż prawdziwy przebieg, na przykład samym tekstem:
    trasy i testy oparte na atrapie sprawdzałyby wtedy coś, czego produkcja nie robi."""
    state = graph.STATE(**await graph.build_fake_graph().ainvoke(graph.example_state()))
    call  = state.messages[-1].tool_calls[0]

    assert call.name      == graph.RESPOND_TOOL_NAME
    assert call.arguments == state.output.model_dump(mode="json", exclude=set(filled_by(graph)))


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
def test_the_respond_tool_follows_the_convention(graph: ModuleType) -> None:
    """Sprawdza, czy narzędzie odpowiedzi każdego grafu nazywa się `respond_<graf>`, a jego schemat
    ma dokładnie te pola wyniku, które podaje model: bez listy źródeł (`sources`), bez notatki
    z kodu pisanej dla programisty i bez komentarzy redakcyjnych w opisie.

    Wyłapuje schemat rozjechany z wynikiem grafu oraz listę źródeł w odpowiedzi modelu: źródła mają
    pochodzić z tego, co agent odczytał, a nie z jego deklaracji."""
    tool     = graph.respond_tool()
    expected = set(output_type(graph).model_fields) - set(filled_by(graph))

    assert tool.name == f"respond_{name_of(graph)}"
    assert set(tool.parameters.get("properties", {})) == expected
    assert "sources"     not in tool.parameters.get("properties", {})
    assert "description" not in tool.parameters
    assert "<!--"        not in tool.description


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
def test_both_prompt_turns_name_the_respond_tool(graph: ModuleType) -> None:
    """Sprawdza, czy prompt systemowy i tura użytkownika każdego grafu wymieniają narzędzie
    odpowiedzi pod nazwą, jaką ma ono dziś w kodzie.

    Wyłapuje zmianę nazwy narzędzia w kodzie bez poprawienia promptu: prompt kazałby wtedy
    odpowiedzieć narzędziem, którego model nie dostał, a w diffie promptu nie byłoby tego widać."""
    assert graph.RESPOND_TOOL_NAME in graph.system_prompt()
    assert graph.RESPOND_TOOL_NAME in graph.user_prompt(anonymized_state(graph))


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_prompts_reach_the_model_clean(graph: ModuleType) -> None:
    """Sprawdza, czy w obu turach promptu każdego grafu nie ma komentarzy redakcyjnych (`<!--`),
    a w turze użytkownika nie zostaje niewypełnione miejsce na dane (`{{…}}`).

    Wyłapuje prompt, w którym do modelu dotarłaby notatka pisana dla nas albo goły znacznik zamiast
    treści zgłoszenia czy reguł."""
    user = graph.user_prompt(anonymized_state(graph))

    assert "<!--" not in graph.system_prompt()
    assert "<!--" not in user
    assert "{{"   not in user


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_prompt_takes_the_text_from_anonymization_only(graph: ModuleType) -> None:
    """Sprawdza, czy tura użytkownika każdego grafu zawiera tekst po anonimizacji (tu znacznik
    wstawiony w jego miejsce) i nie zawiera surowej treści zgłoszenia.

    Wyłapuje prompt, który bierze treść z wejścia sprzed anonimizacji: dane klienta wyszłyby wtedy
    do zewnętrznego modelu."""
    state = anonymized_state(graph)
    user  = graph.user_prompt(state)

    assert ANONYMIZED            in user
    assert state.input_text  not in user


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_prompt_refuses_a_state_before_anonymization(graph: ModuleType) -> None:
    """Sprawdza, czy złożenie tury użytkownika ze stanu, który nie przeszedł jeszcze anonimizacji,
    kończy się błędem w każdym grafie.

    Wyłapuje źle złożony graf, w którym model ruszałby przed anonimizacją: zamiast błędu powstałby
    prompt z pustym zgłoszeniem."""
    with pytest.raises(ValueError):
        graph.user_prompt(graph.example_state())


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_user_turn_carries_no_instructions(graph: ModuleType) -> None:
    """Sprawdza, czy szablon tury użytkownika każdego grafu to same dane i krótkie rusztowanie: nie
    ma w nim nagłówków sekcji, a po odjęciu miejsc na dane zostaje mniej niż 600 znaków.

    Wyłapuje reguły, które wróciły do tury użytkownika: instrukcja ma stać w turze systemowej
    i w opisie narzędzia odpowiedzi, także w prompcie parsującym, żeby nie mieszała się z wklejoną
    treścią zgłoszenia."""
    template    = graph.graph.read_document(graph.graph.USER_FILE)
    scaffolding = re.sub(r"\{\{\w+\}\}", "", template)

    assert "## " not in template
    assert len(scaffolding) < 600, "instrukcje wracają do tury użytkownika"


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_model_sees_exactly_the_allowed_tools(graph: ModuleType) -> None:
    """Sprawdza, czy model w każdym grafie dostaje definicje dokładnie tych narzędzi wiedzy, które
    graf dopuszcza, w tej samej kolejności, a po nich narzędzie odpowiedzi, jeśli graf je ma.
    W opisach nie może być komentarzy redakcyjnych ani niewypełnionych miejsc `{{…}}`.

    Wyłapuje graf, który gubi narzędzie, zmienia ich kolejność albo wysyła modelowi opis z notatką
    dla nas czy z gołym znacznikiem zamiast limitu wywołań."""
    respond     = [graph.RESPOND_TOOL_NAME] if graph in RESPOND_GRAPHS else []
    definitions = graph.model_tools(allowed_tools(graph), LIMITS)

    assert [definition.name for definition in definitions] == [*graph.TOOL_NAMES, *respond]
    assert all("<!--" not in definition.description for definition in definitions)
    assert all("{{" not in definition.description for definition in definitions)


@pytest.mark.parametrize(
    "graph",
    [graph for graph in GRAPHS if graph.TOOL_NAMES],
    ids=name_of,
)
def test_every_tool_of_the_graph_tells_the_model_its_call_limit(graph: ModuleType) -> None:
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy opis każdego narzędzia podaje modelowi
    jego limit wywołań z domyślnej konfiguracji.

    Wyłapuje narzędzie, którego opis limitu nie podaje albo podaje inny niż konfiguracja: ten sam
    limit egzekwuje `run_tools`, więc model dowiadywałby się o nim dopiero z odmowy."""
    definitions = graph.model_tools(allowed_tools(graph), LIMITS)

    for definition in definitions:
        if definition.name in graph.TOOL_NAMES:
            expected = f"Limit wywołań w jednej sprawie: {LIMITS[definition.name]}."

            assert expected in definition.description, definition.name


@pytest.mark.parametrize(
    "graph",
    [graph for graph in GRAPHS if "find_tickets_vector" not in graph.TOOL_NAMES],
    ids=name_of,
)
def test_a_tool_outside_the_list_is_refused(graph: ModuleType) -> None:
    """Sprawdza, czy graf, który nie ma wyszukiwania zgłoszeń (`find_tickets_vector`) na liście
    dozwolonych narzędzi, odmawia złożenia definicji, gdy mimo to je dostanie.

    Wyłapuje cichy dostęp do indeksu zgłoszeń w grafach, które mają działać bez niego: bramki
    i „Popraw" muszą działać także przy pustym indeksie."""
    with pytest.raises(ValueError):
        graph.model_tools([FakeFindTicketsVectorTool()], LIMITS)


@pytest.mark.parametrize(
    "graph",
    [graph for graph in GRAPHS if graph.TOOL_NAMES],
    ids=name_of,
)
async def test_the_turn_limit_cuts_the_loop_of_every_tool_graph(graph: ModuleType) -> None:
    """Sprawdza, czy każdy graf z narzędziami wiedzy, uruchomiony na atrapach z limitem jednej tury,
    po pierwszej turze modelu nie wykonuje narzędzi, tylko idzie prosto do odpowiedzi.

    Wyłapuje nowy graf z pętlą, w którym zapomniano o limicie tur: model, który ciągle woła
    narzędzia, krążyłby w nim bez końca."""
    compiled = graph.build_fake_graph(max_iterations=1)
    state    = graph.STATE(**await compiled.ainvoke(graph.example_state()))

    assert [entry.node for entry in state.log] == ["anonymize", "agent", "respond"]
    assert state.iterations == 1


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_sources_exist_exactly_where_knowledge_tools_do(graph: ModuleType) -> None:
    """Sprawdza, czy stan każdego grafu z narzędziami wiedzy ma listę źródeł (`sources`) łączoną
    funkcją `merge_sources`, a stan grafu bez takich narzędzi nie ma jej wcale.

    Wyłapuje graf, który zadeklarował listę źródeł bez tej funkcji: każdy kolejny odczyt po cichu
    nadpisywałby wtedy źródła z poprzednich, zamiast je doklejać."""
    hints = get_type_hints(type(graph.example_state()), include_extras=True)

    if not graph.TOOL_NAMES:
        assert "sources" not in hints
        return

    assert hints["sources"].__metadata__ == (merge_sources,)


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_example_state_is_the_graph_state(graph: ModuleType) -> None:
    """Sprawdza, czy stan przykładowy każdego grafu jest obiektem klasy `STATE`, czyli tej samej,
    z której trasy budują stan wejściowy.

    Wyłapuje graf, w którym stan przykładowy i klasa stanu się rozeszły: testy na stanie
    przykładowym sprawdzałyby wtedy inny kształt niż ten, którego używa aplikacja."""
    assert isinstance(graph.example_state(), graph.STATE)


def test_only_the_solution_variant_requires_hits() -> None:
    """Sprawdza, czy każdy wariant propozycji (`suggest_*`) ma etykietę guzika i deklaruje, czy
    wymaga źródeł: wymaga ich tylko rozwiązanie, a pytania i przekazanie sprawy nie.

    Wyłapuje przestawioną deklarację: rozwiązanie bez wymogu źródeł mogłoby powstać „z głowy",
    a pytania i przekazanie sprawy przestałyby działać przy pustym indeksie. Nowy wariant też trzeba
    tu świadomie dopisać."""
    assert all(graph.LABEL for graph in GRAPHS if name_of(graph).startswith("suggest_"))

    declared = {
        name_of(graph): graph.REQUIRES_HITS
        for graph in GRAPHS
        if name_of(graph).startswith("suggest_")
    }

    assert declared == {
        "suggest_handoff":   False,
        "suggest_questions": False,
        "suggest_solution":  True,
    }
