import operator
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.anonymization import AnonymizedText
from app.llm import ChatMessage, ToolDefinition
from app.nodes import LogEntry
from app.tools import KnowledgeSource, SourceRef
from app.util.json_schema import json_schema_without_docs
from app.util.markdown import read_document


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
    current: list[SourceRef],  # np. [SourceRef(source="find_tickets", item_id="90001", …)]
    new:     list[SourceRef],  # np. [SourceRef(source="find_tickets", item_id="90001", …), …]
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
    state:             GraphState,  # np. SearchState(messages=[tool_call_turn("find_tickets", …)])
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
        state=SearchState(messages=[tool_call_turn("find_tickets", {…})], …)
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
    tools:     Sequence[KnowledgeSource],  # np. [FakeFindTickets(), FakeFindDocs()]
    allowed:   Sequence[str],              # np. ("find_tickets", "find_docs")
    graph_dir: Path,                       # np. Path("/code/app/graph/search")
) -> list[ToolDefinition]:
    """
    Description:
    Definicje narzędzi wiedzy dla modelu w danym grafie: nazwa narzędzia, opis z
    `<graph_dir>/<nazwa>.md` i schemat `query_model` bez dokumentacji. Opis leży w grafie, nie
    w `tools/`, bo to treść promptu i różni się między grafami używającymi tego samego narzędzia.

    Example args:
        tools=[FakeFindTickets()]
        allowed=("find_tickets", "find_docs")
        graph_dir=Path("/code/app/graph/search")

    Example result:
        [ToolDefinition(name="find_tickets", description="Szuka historycznych zgłoszeń…", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych dla tego grafu
    """
    forbidden = [tool.name for tool in tools if tool.name not in allowed]

    if forbidden:
        raise ValueError(f"narzędzia spoza listy dozwolonych dla grafu: {forbidden}")

    definitions = [
        ToolDefinition(
            name        = tool.name,
            description = read_document(graph_dir / f"{tool.name}.md").rstrip(),
            parameters  = json_schema_without_docs(tool.query_model),
        )
        for tool in tools
    ]

    return definitions
