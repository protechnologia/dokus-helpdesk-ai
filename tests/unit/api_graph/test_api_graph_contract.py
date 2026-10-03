import importlib
import pkgutil
import re
from types import ModuleType
from typing import get_args, get_type_hints

import pytest
from pydantic import BaseModel

import app.graph
from app.anonymization import AnonymizedText
from app.graph import merge_sources
from app.tools.docs.find_docs_text.fake import FakeFindDocsTextTool
from app.tools.docs.find_docs_vector.fake import FakeFindDocsVectorTool
from app.tools.docs.list_docs.fake import FakeListDocsTool
from app.tools.docs.read_docs.fake import FakeReadDocsTool
from app.tools.tickets.find_tickets_text.fake import FakeFindTicketsTextTool
from app.tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool


def all_graphs() -> list[ModuleType]:
    """
    Description:
    Zbiera pakiety grafów z `app/graph/` — także tych, których jeszcze nie ma. Nowy graf to nowy
    katalog, więc test ma go znaleźć sam.

    Example args:
        (brak)

    Example result:
        [<module app.graph.gate_close>, <module app.graph.gate_reply>, …]
    """
    graphs = [
        importlib.import_module(f"app.graph.{module.name}")
        for module in pkgutil.iter_modules(app.graph.__path__)
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
    FakeListDocsTool(),
    FakeFindDocsVectorTool(),
    FakeFindDocsTextTool(),
    FakeReadDocsTool(),
]

# Znacznik zamiast tekstu po anonimizacji — gdy jest w prompcie, a tekstu surowego nie ma, prompt
# wziął treść z `anonymized`.
ANONYMIZED = "ZANONIMIZOWANE-7f3a"


def name_of(
    graph: ModuleType,  # np. <module app.graph.gate_close>
) -> str:
    """
    Description:
    Nazwa grafu = nazwa jego katalogu.

    Example args:
        graph=<module app.graph.gate_close>

    Example result:
        "gate_close"
    """
    return graph.__name__.split(".")[-1]


def output_type(
    graph: ModuleType,  # np. <module app.graph.gate_close>
) -> type[BaseModel]:
    """
    Description:
    Typ wyniku grafu, odczytany z pola `output` jego stanu.

    Example args:
        graph=<module app.graph.gate_close>

    Example result:
        Verdict
    """
    annotation = graph.STATE.model_fields["output"].annotation
    found      = [arg for arg in get_args(annotation) if arg is not type(None)]

    return found[0]


def anonymized_state(
    graph: ModuleType,  # np. <module app.graph.gate_close>
) -> BaseModel:
    """
    Description:
    Przykładowy stan grafu po anonimizacji, w którym tekst zanonimizowany to znacznik.

    Example args:
        graph=<module app.graph.gate_close>

    Example result:
        GateCloseState(input_text="Nie przychodzą…", anonymized=AnonymizedText(text="ZANON…"), …)
    """
    state = graph.example_state().model_copy(update={"anonymized": AnonymizedText(text=ANONYMIZED)})

    return state


def filled_by(
    graph: ModuleType,  # np. <module app.graph.parse_ticket>
) -> tuple[str, ...]:
    """
    Description:
    Pola wyniku, których model nie podaje, bo wypełnia je graf — dziś tylko w `parse_ticket`.

    Example args:
        graph=<module app.graph.parse_ticket>

    Example result:
        ("ticket_id", "date", "resolution_vocabulary_version")
    """
    return getattr(graph, "FILLED_BY_GRAPH", ())


def allowed_tools(
    graph: ModuleType,  # np. <module app.graph.search>
) -> list:
    """
    Description:
    Atrapy narzędzi z listy dozwolonych dla grafu.

    Example args:
        graph=<module app.graph.search>

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeListDocsTool(), …]
    """
    return [tool for tool in AGENT_TOOLS if tool.name in graph.TOOL_NAMES]


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_every_graph_exposes_the_same_api(graph: ModuleType) -> None:
    """Pakiet grafu → ta sama para promptów, definicje narzędzi, przebieg, atrapa i stan
    przykładowy: trasy, CLI i węzeł `agent` sięgają po nie tak samo w każdym grafie."""
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
    """Atrapa grafu na stanie przykładowym → wynik w typie grafu, pierwszy wpis logu od
    `anonymize`, ostatni od `respond`."""
    state_type = type(graph.example_state())
    state      = state_type(**await graph.build_fake_graph().ainvoke(graph.example_state()))

    assert isinstance(state.output, output_type(graph))
    assert state.log[0].node  == "anonymize"
    assert state.log[-1].node == "respond"


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
async def test_the_fake_agent_answers_through_the_respond_tool(graph: ModuleType) -> None:
    """Ostatnia tura atrapy agenta → wywołanie `respond_<graf>`, którego argumenty to wynik bez
    pól, które wypełnia graf."""
    state = graph.STATE(**await graph.build_fake_graph().ainvoke(graph.example_state()))
    call  = state.messages[-1].tool_calls[0]

    assert call.name      == graph.RESPOND_TOOL_NAME
    assert call.arguments == state.output.model_dump(mode="json", exclude=set(filled_by(graph)))


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
def test_the_respond_tool_follows_the_convention(graph: ModuleType) -> None:
    """Narzędzie odpowiedzi → `respond_<graf>`, schemat to dokładnie pola wyniku (bez `sources`,
    bo źródła daje `cite()`), bez docstringów i komentarzy redakcyjnych."""
    tool     = graph.respond_tool()
    expected = set(output_type(graph).model_fields) - set(filled_by(graph))

    assert tool.name == f"respond_{name_of(graph)}"
    assert set(tool.parameters.get("properties", {})) == expected
    assert "sources"     not in tool.parameters.get("properties", {})
    assert "description" not in tool.parameters
    assert "<!--"        not in tool.description


@pytest.mark.parametrize("graph", RESPOND_GRAPHS, ids=name_of)
def test_both_prompt_turns_name_the_respond_tool(graph: ModuleType) -> None:
    """Prompt każe odpowiedzieć narzędziem → pod jego aktualną nazwą: zmiana nazwy w kodzie bez
    promptu nie jest widoczna w diffie promptu."""
    assert graph.RESPOND_TOOL_NAME in graph.system_prompt()
    assert graph.RESPOND_TOOL_NAME in graph.user_prompt(anonymized_state(graph))


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_prompts_reach_the_model_clean(graph: ModuleType) -> None:
    """Obie tury promptu → bez komentarzy redakcyjnych i bez niewypełnionego miejsca na dane."""
    user = graph.user_prompt(anonymized_state(graph))

    assert "<!--" not in graph.system_prompt()
    assert "<!--" not in user
    assert "{{"   not in user


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_prompt_takes_the_text_from_anonymization_only(graph: ModuleType) -> None:
    """Stan po anonimizacji → w prompcie tekst zanonimizowany, a surowego `input_text` nie ma."""
    state = anonymized_state(graph)
    user  = graph.user_prompt(state)

    assert ANONYMIZED            in user
    assert state.input_text  not in user


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_prompt_refuses_a_state_before_anonymization(graph: ModuleType) -> None:
    """Stan bez `anonymized` → błąd, a nie prompt z pustym zgłoszeniem: graf jest źle złożony."""
    with pytest.raises(ValueError):
        graph.user_prompt(graph.example_state())


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_user_turn_carries_no_instructions(graph: ModuleType) -> None:
    """Szablon tury użytkownika → dane i rusztowanie, bez reguł: instrukcja stoi w turze
    systemowej i w opisie narzędzia odpowiedzi, także w prompcie parsującym."""
    template    = graph.graph.read_document(graph.graph.USER_FILE)
    scaffolding = re.sub(r"\{\{\w+\}\}", "", template)

    assert "## " not in template
    assert len(scaffolding) < 600, "instrukcje wracają do tury użytkownika"


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_model_sees_exactly_the_allowed_tools(graph: ModuleType) -> None:
    """Narzędzia wiedzy z listy dozwolonych → po definicji na każde (opis z katalogu narzędzia,
    bez komentarzy redakcyjnych), a na końcu narzędzie odpowiedzi, jeśli graf je ma."""
    respond     = [graph.RESPOND_TOOL_NAME] if graph in RESPOND_GRAPHS else []
    definitions = graph.model_tools(allowed_tools(graph))

    assert [definition.name for definition in definitions] == [*graph.TOOL_NAMES, *respond]
    assert all("<!--" not in definition.description for definition in definitions)


@pytest.mark.parametrize(
    "graph",
    [graph for graph in GRAPHS if "find_tickets_vector" not in graph.TOOL_NAMES],
    ids=name_of,
)
def test_a_tool_outside_the_list_is_refused(graph: ModuleType) -> None:
    """Graf bez `find_tickets_vector` na liście dozwolonych → podanie go to błąd składania, nie
    cichy dostęp do indeksu (bramki i „Popraw" mają działać przy pustym indeksie)."""
    with pytest.raises(ValueError):
        graph.model_tools([FakeFindTicketsVectorTool()])


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_sources_exist_exactly_where_knowledge_tools_do(graph: ModuleType) -> None:
    """Graf z narzędziami wiedzy → pole `sources` z reduktorem `merge_sources`; graf bez nich →
    bez `sources`, bo nie ma czego cytować."""
    hints = get_type_hints(type(graph.example_state()), include_extras=True)

    if not graph.TOOL_NAMES:
        assert "sources" not in hints
        return

    assert hints["sources"].__metadata__ == (merge_sources,)


@pytest.mark.parametrize("graph", GRAPHS, ids=name_of)
def test_the_example_state_is_the_graph_state(graph: ModuleType) -> None:
    """Stan przykładowy z atrapy → instancja `STATE`, czyli klasy, z której trasy budują stan."""
    assert isinstance(graph.example_state(), graph.STATE)


def test_only_the_solution_variant_requires_hits() -> None:
    """Warianty `suggest_*` → każdy deklaruje etykietę guzika i `REQUIRES_HITS`; trafień wymaga
    tylko `solution` (zasada 9), pytania i przekazanie działają przy pustym indeksie."""
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
