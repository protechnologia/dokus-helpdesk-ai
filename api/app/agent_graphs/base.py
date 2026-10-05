import operator
from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.agent_nodes import LogEntry
from app.agent_tools import AgentTool, SourceRef
from app.agent_tools.base import arguments_model_of
from app.core_util.json_schema import json_schema_without_docs
from app.engine_anonymization import AnonymizedText
from app.engine_llm import ChatMessage, LLMUsage, ToolDefinition


def add_usage(
    current: LLMUsage,  # np. LLMUsage(calls=1, prompt_tokens=4820, cost_usd=0.0321)
    new:     LLMUsage,  # np. LLMUsage(calls=1, prompt_tokens=5100, cost_usd=0.0214)
) -> LLMUsage:
    """
    Description:
    Reduktor pola `usage` w stanie grafu: dodaje zużycie modelu z kolejnej tury do dotychczasowej
    sumy. Węzeł `agent` zwraca zużycie SWOJEJ tury, a nie sumę — sumuje stan.

    Example args:
        current=LLMUsage(calls=1, prompt_tokens=4820, cost_usd=0.0321)
        new=LLMUsage(calls=1, prompt_tokens=5100, cost_usd=0.0214)

    Example result:
        LLMUsage(calls=2, prompt_tokens=9920, cost_usd=0.0535)
    """
    return current.plus(new)


class GraphState(BaseModel):
    """
    Description:
    Pola stanu, które czytają albo piszą wspólne węzły każdego grafu: wejście, jego wersja po
    anonimizacji, rozmowa z modelem, licznik tur, licznik poprawek odpowiedzi, zużycie modelu
    i log przebiegu.

    Do czego:
    `state.py` każdego grafu dziedziczy po tej klasie i dokłada własne pola — `output` w typie
    swojego wyniku, `sources` w grafach z narzędziami wiedzy, dane wejściowe jak `rules`.
    Reduktory list wspólnych są zadeklarowane raz, tutaj, więc żaden graf nie zgubi ich po cichu.

    Nie typuj tą klasą żadnego pola ani listy w modelu Pydantic: `model_dump()` zrzuca z takiego
    pola wyłącznie pola bazowe i gubi resztę bez błędu (sprawdzone na Pydanticu 2.10).
    """

    model_config = ConfigDict(extra="forbid")

    input_text:      str                                        = Field(min_length=1)          # wejście surowe; do modelu idzie wyłącznie `anonymized`
    anonymized:      AnonymizedText | None                      = None                         # ustawia węzeł `anonymize`
    messages:        Annotated[list[ChatMessage], operator.add] = Field(default_factory=list)  # rozmowa z modelem; reduktor dokleja nowe wiadomości
    iterations:      int                                        = 0                            # liczba tur modelu; podbija węzeł `agent`
    respond_retries: int                                        = 0                            # ile razy węzeł `respond` odesłał odpowiedź do poprawki
    usage:           Annotated[LLMUsage, add_usage]             = Field(default_factory=LLMUsage)  # tokeny i koszt wywołań modelu; reduktor sumuje tury
    log:             Annotated[list[LogEntry], operator.add]    = Field(default_factory=list)  # przebieg: po wpisie od każdego wywołania węzła


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
    max_iterations:    int,         # np. 20 — limit tur modelu z `AGENT_MAX_ITERATIONS`
) -> Literal["run_tools", "respond"]:
    """
    Description:
    Rozgałęzienie po turze modelu w grafie z narzędziami. Dokąd idzie przebieg, rozstrzyga to, co
    model wywołał, i limit tur:

    | ostatnia tura modelu                           | dokąd                                 |
    |------------------------------------------------|---------------------------------------|
    | same narzędzia wiedzy, limit tur niewyczerpany | `run_tools`, a potem znowu `agent`    |
    | narzędzie odpowiedzi                           | `respond`                             |
    | sam tekst albo odpowiedź z innym narzędziem    | `respond` — błąd formatu              |
    | narzędzia wiedzy w ostatniej dozwolonej turze  | `respond` — narzędzia już nie ruszają |

    Błędy formatu i turę uciętą limitem rozstrzyga `respond`, więc tu nie giną: odsyła je modelowi
    do poprawki, jeden raz. Limit liczy tury modelu (`iterations`), nie wywołania narzędzi — te
    mają własne limity w `run_tools`.

    Example args:
        state=SearchState(messages=[tool_call_turn("find_tickets_vector", {…})], iterations=1, …)
        respond_tool_name="respond_search"
        max_iterations=20

    Example result:
        "run_tools"
    """
    calls = state.messages[-1].tool_calls if state.messages else []
    names = {call.name for call in calls}

    # --- odpowiedź albo sam tekst: koniec pętli ---
    if not names or respond_tool_name in names:
        return "respond"

    # --- limit tur wyczerpany: model nie dostanie już kolejnej tury, więc narzędzi nie wykonujemy ---
    if state.iterations >= max_iterations:
        return "respond"

    # --- same narzędzia wiedzy: kolejny obieg ---
    return "run_tools"


def route_after_respond(
    state: GraphState,  # np. GateCloseState(messages=[…, ChatMessage(role="tool", …)], …)
) -> Literal["agent", "__end__"]:
    """
    Description:
    Rozgałęzienie po węźle `respond` w każdym grafie: koniec przebiegu albo jeszcze jedna tura
    modelu. Rozstrzyga ostatnia wiadomość rozmowy — gdy nie jest turą modelu, model jest winien
    odpowiedź na to, co odesłał mu `respond`.

    | co zrobił `respond`                               | ostatnia wiadomość | dokąd   |
    |---------------------------------------------------|--------------------|---------|
    | przyjął odpowiedź i zapisał wynik                 | tura modelu        | koniec  |
    | skończył bez wyniku: graf wymaga źródeł, brak ich | tura modelu        | koniec  |
    | odesłał odpowiedź do poprawki                     | `tool` albo `user` | `agent` |

    Pętli tu nie ma: poprawka jest jedna na sprawę, a drugą odpowiedź nie do przyjęcia węzeł
    `respond` kończy błędem, zanim przebieg wróci do tego rozgałęzienia.

    Example args:
        state=GateCloseState(messages=[tool_call_turn("respond_gate_close", {…}),
                                       ChatMessage(role="tool", call_id="call_1", content="…")], …)

    Example result:
        "agent"
    """
    # --- rozmowa czeka na turę modelu: `respond` odesłał odpowiedź do poprawki ---
    if state.messages and state.messages[-1].role != "assistant":
        return "agent"

    # --- rozmowa kończy się turą modelu: wynik zapisany albo świadomie go nie ma ---
    return END


# Miejsce w opisie narzędzia (`description.md`), w które wchodzi jego limit wywołań.
MAX_CALLS_PLACEHOLDER = "{{max_calls}}"


def tool_definitions(
    tools:   Sequence[AgentTool],  # np. [FakeFindTicketsVectorTool(), FakeListDocsTool()]
    allowed: Sequence[str],        # np. ("find_tickets_vector", "list_docs")
    limits:  Mapping[str, int],    # np. {"find_tickets_vector": 3, "list_docs": 1}
) -> list[ToolDefinition]:
    """
    Description:
    Definicje narzędzi dla modelu w danym grafie: nazwa narzędzia, jego opis i schemat argumentów
    bez dokumentacji — `query_model` źródła wiedzy albo `args_model` narzędzia pomocniczego. Opis
    należy do narzędzia (`description.md` w jego katalogu) i jest ten sam w każdym grafie; graf
    decyduje tylko, które narzędzia model widzi. W opis wchodzi limit wywołań narzędzia z
    konfiguracji — ten sam, który egzekwuje `run_tools` — więc model wie z góry, ile wywołań ma.

    Example args:
        tools=[FakeFindTicketsVectorTool()]
        allowed=("find_tickets_vector", "find_docs_vector")
        limits={"find_tickets_vector": 3}

    Example result:
        [ToolDefinition(name="find_tickets_vector", description="Szuka historycznych zgłoszeń…", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych dla tego grafu albo bez limitu wywołań
    """
    forbidden = [tool.name for tool in tools if tool.name not in allowed]

    if forbidden:
        raise ValueError(f"narzędzia spoza listy dozwolonych dla grafu: {forbidden}")

    # Bez limitu opis poszedłby do modelu z niewypełnionym miejscem.
    unlimited = [tool.name for tool in tools if tool.name not in limits]

    if unlimited:
        raise ValueError(f"narzędzia bez limitu wywołań (AGENT_MAX_CALLS_*): {unlimited}")

    definitions = [
        ToolDefinition(
            name        = tool.name,
            description = tool.description.replace(MAX_CALLS_PLACEHOLDER, str(limits[tool.name])),
            parameters  = json_schema_without_docs(arguments_model_of(tool)),
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
