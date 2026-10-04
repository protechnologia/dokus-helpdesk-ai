import operator
from collections.abc import Sequence
from typing import Annotated, Literal

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.agent_nodes import LogEntry
from app.agent_tools import AgentTool, KnowledgeSource, SourceRef
from app.core_util.json_schema import json_schema_without_docs
from app.engine_anonymization import AnonymizedText
from app.engine_llm import ChatMessage, ToolDefinition


class GraphState(BaseModel):
    """
    Description:
    Pola stanu, które czytają albo piszą wspólne węzły każdego grafu: wejście, jego wersja po
    anonimizacji, rozmowa z modelem, licznik tur i log przebiegu.

    Do czego:
    `state.py` każdego grafu dziedziczy po tej klasie i dokłada własne pola — `output` w typie
    swojego wyniku, `sources` w grafach z narzędziami wiedzy, dane wejściowe jak `rules`.
    Reduktory list wspólnych są zadeklarowane raz, tutaj, więc żaden graf nie zgubi ich po cichu.

    Nie typuj tą klasą żadnego pola ani listy w modelu Pydantic: `model_dump()` zrzuca z takiego
    pola wyłącznie pola bazowe i gubi resztę bez błędu (sprawdzone na Pydanticu 2.10).
    """

    model_config = ConfigDict(extra="forbid")

    input_text: str                                        = Field(min_length=1)          # wejście surowe; do modelu idzie wyłącznie `anonymized`
    anonymized: AnonymizedText | None                      = None                         # ustawia węzeł `anonymize`
    messages:   Annotated[list[ChatMessage], operator.add] = Field(default_factory=list)  # rozmowa z modelem; reduktor dokleja nowe wiadomości
    iterations: int                                        = 0                            # liczba tur modelu; podbija węzeł `agent`
    log:        Annotated[list[LogEntry], operator.add]    = Field(default_factory=list)  # przebieg: po wpisie od każdego wywołania węzła


def merge_sources(
    current: list[SourceRef],  # np. [SourceRef(source="tickets", item_id="90001", …)]
    new:     list[SourceRef],  # np. [SourceRef(source="tickets", item_id="90001", …), …]
) -> list[SourceRef]:
    """
    Description:
    Reduktor pola `sources` w stanie grafu: dokleja nowe źródła, pomijając te, których klucz już
    jest. Agent może szukać kilka razy i trafić na to samo zgłoszenie — na liście źródeł ma się
    ono znaleźć raz, z pierwszego trafienia.

    `sources` nie ma w `GraphState`, bo mają je tylko grafy z narzędziami wiedzy: taki graf
    deklaruje pole w swoim `state.py` jako `Annotated[list[SourceRef], merge_sources]`, a test
    grafów (p. 12) pilnuje, że żaden o tym nie zapomniał.

    Example args:
        current=[SourceRef(…, item_id="90001")]
        new=[SourceRef(…, item_id="90001"), SourceRef(…, item_id="90002")]

    Example result:
        [SourceRef(…, item_id="90001"), SourceRef(…, item_id="90002")]
    """
    seen = {ref.key for ref in current}

    return current + [ref for ref in new if ref.key not in seen]


def route_after_agent(
    state:             GraphState,  # np. SearchState(messages=[tool_call_turn("find_tickets_vector", …)])
    respond_tool_name: str,         # np. "respond_search"
) -> Literal["run_tools", "respond"]:
    """
    Description:
    Rozgałęzienie po turze modelu w grafie z narzędziami: dokąd idzie przebieg, rozstrzyga to, co
    model wywołał. Narzędzia wiedzy → `run_tools` (i z powrotem do `agent`); narzędzie odpowiedzi
    albo brak wywołań → `respond`. Tura bez wywołań i tura łącząca odpowiedź z innym narzędziem to
    błędy formatu — rozstrzyga je `respond` (p. 11), więc tu nie giną. Limit iteracji dochodzi
    z węzłem `agent` (p. 9).

    Example args:
        state=SearchState(messages=[tool_call_turn("find_tickets_vector", {…})], …)
        respond_tool_name="respond_search"

    Example result:
        "run_tools"
    """
    calls = state.messages[-1].tool_calls if state.messages else []
    names = {call.name for call in calls}

    # --- odpowiedź albo sam tekst: koniec pętli ---
    if not names or respond_tool_name in names:
        return "respond"

    # --- same narzędzia wiedzy: kolejny obieg ---
    return "run_tools"


def tool_definitions(
    tools:   Sequence[AgentTool],  # np. [FakeFindTicketsVectorTool(), FakeListDocsTool()]
    allowed: Sequence[str],        # np. ("find_tickets_vector", "list_docs")
) -> list[ToolDefinition]:
    """
    Description:
    Definicje narzędzi dla modelu w danym grafie: nazwa narzędzia, jego opis i schemat argumentów
    bez dokumentacji — `query_model` źródła wiedzy albo `args_model` narzędzia pomocniczego. Opis
    należy do narzędzia (`description.md` w jego katalogu) i jest ten sam w każdym grafie; graf
    decyduje tylko, które narzędzia model widzi.

    Example args:
        tools=[FakeFindTicketsVectorTool()]
        allowed=("find_tickets_vector", "find_docs_vector")

    Example result:
        [ToolDefinition(name="find_tickets_vector", description="Szuka historycznych zgłoszeń…", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych dla tego grafu
    """
    forbidden = [tool.name for tool in tools if tool.name not in allowed]

    if forbidden:
        raise ValueError(f"narzędzia spoza listy dozwolonych dla grafu: {forbidden}")

    definitions = [
        ToolDefinition(
            name        = tool.name,
            description = tool.description,
            parameters  = json_schema_without_docs(
                # oba rodzaje trzymają model argumentów pod inną nazwą
                tool.query_model if isinstance(tool, KnowledgeSource) else tool.args_model
            ),
        )
        for tool in tools
    ]

    return definitions


async def run_graph(
    graph: CompiledStateGraph,  # np. gate_close.build_fake_graph()
    state: BaseModel,           # np. GateCloseState(input_text="…", rules=["…"])
) -> BaseModel:
    """
    Description:
    Przepuszcza stan wejściowy przez graf i oddaje stan końcowy jako model tej samej klasy.
    LangGraph zwraca słownik pól, a trasy czytają `output`, `sources` i `messages` z modelu.

    Example args:
        graph=gate_close.build_fake_graph()
        state=GateCloseState(input_text="Nie przychodzą przesyłki…", rules=["…"])

    Example result:
        GateCloseState(…, output=Verdict(verdict="pass", …), log=[LogEntry(…), …])
    """
    result = await graph.ainvoke(state)

    final = type(state)(**result)

    return final
