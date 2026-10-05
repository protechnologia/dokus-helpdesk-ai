import pytest

from app.agent_graphs import GraphState, merge_sources, route_after_agent, tool_definitions
from app.agent_graphs.base import MAX_CALLS_PLACEHOLDER
from app.agent_nodes.agent import tool_call_turn
from app.agent_tools import SourceRef
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.engine_llm import ChatMessage


def make_ref(
    item_id: str = "90001",  # np. "90002"
) -> SourceRef:
    """
    Description:
    Buduje źródło z odczytu zgłoszenia, różniące się tylko id.

    Example args:
        item_id="90001"

    Example result:
        SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")
    """
    return SourceRef(source="tickets", item_id=item_id, title="Brak przesyłek")


def test_merge_sources_skips_what_is_already_there() -> None:
    """Sprawdza, czy zgłoszenie odczytane drugi raz nie trafia na listę źródeł ponownie: zostaje na
    niej raz, na dotychczasowym miejscu, a nowe źródło dochodzi na koniec listy.

    Wyłapuje powtórzenia na liście źródeł: agent może przeczytać to samo zgłoszenie kilka razy,
    a człowiek zobaczyłby je wtedy w odpowiedzi wielokrotnie."""
    current = [make_ref("90001")]
    new     = [make_ref("90001"), make_ref("90002")]

    assert [ref.item_id for ref in merge_sources(current, new)] == ["90001", "90002"]


def test_merge_sources_keeps_the_same_id_from_another_tool() -> None:
    """Sprawdza, czy zgłoszenie i sekcja dokumentacji o tym samym identyfikatorze (tu „33644")
    zostają na liście źródeł jako dwa osobne wpisy.

    Wyłapuje rozpoznawanie źródeł po samym identyfikatorze, bez rodzaju materiału: sekcja
    dokumentacji znikałaby wtedy z listy źródeł, gdy jej identyfikator pokryje się z numerem
    zgłoszenia."""
    ticket   = make_ref("33644")
    fragment = SourceRef(source="docs", item_id="33644", title="Instrukcja 4.12")

    assert len(merge_sources([ticket], [fragment])) == 2


SEARCH  = tool_call_turn("find_tickets_vector", {"problem": "Brak przesyłek", "symptoms": "pusto"})
RESPOND = tool_call_turn("respond_search", {}, call_id="call_2")
TEXT    = ChatMessage(role="assistant", content="Najpierw sprawdzę…")
BOTH    = ChatMessage(role="assistant", tool_calls=[*SEARCH.tool_calls, *RESPOND.tool_calls])


# Limit tur w testach rozgałęzienia — z zapasem tam, gdzie test go nie dotyczy.
MAX_ITERATIONS = 5


def state_after(
    turn:       ChatMessage,  # np. tool_call_turn("find_tickets_vector", {…})
    iterations: int = 1,      # np. 5 — ile tur modelu już było, razem z tą
) -> GraphState:
    """
    Description:
    Stan grafu, którego ostatnia wiadomość to podana tura modelu.

    Example args:
        turn=tool_call_turn("find_tickets_vector", {…})
        iterations=1

    Example result:
        GraphState(input_text="x", messages=[ChatMessage(role="assistant", …)], iterations=1)
    """
    return GraphState(input_text="x", messages=[turn], iterations=iterations)


@pytest.mark.parametrize(
    "turn, target",
    [
        (SEARCH,  "run_tools"),
        (RESPOND, "respond"),
        (TEXT,    "respond"),
        (BOTH,    "respond"),
    ],
    ids=["knowledge-tool", "respond-tool", "text-only", "respond-with-another"],
)
def test_the_route_follows_what_the_model_called(turn: ChatMessage, target: str) -> None:
    """Sprawdza, czy po turze modelu przebieg idzie tam, gdzie wskazuje to, co model wywołał. Samo
    narzędzie wiedzy prowadzi do wykonania narzędzi (`run_tools`). Narzędzie odpowiedzi, sam tekst
    i odpowiedź zgłoszona razem z innym narzędziem prowadzą do węzła odpowiedzi (`respond`).

    Wyłapuje źle poprowadzone rozgałęzienie: wyszukiwanie, które nie zostałoby wykonane, albo turę
    z błędem formatu, która ominęłaby `respond`, choć to on ma taki błąd rozstrzygnąć."""
    route = route_after_agent(
        state_after(turn),
        respond_tool_name = "respond_search",
        max_iterations    = MAX_ITERATIONS,
    )

    assert route == target


@pytest.mark.parametrize(
    "iterations, target",
    [
        (MAX_ITERATIONS - 1, "run_tools"),
        (MAX_ITERATIONS,     "respond"),
        (MAX_ITERATIONS + 1, "respond"),
    ],
    ids=["below-the-limit", "last-allowed-turn", "past-the-limit"],
)
def test_the_turn_limit_stops_the_loop(iterations: int, target: str) -> None:
    """Sprawdza, czy limit tur modelu (tu 5) kończy pętlę: gdy model woła narzędzie wiedzy
    w czwartej turze, narzędzie jest jeszcze wykonywane, a w piątej i w każdej dalszej przebieg
    idzie już do odpowiedzi.

    Wyłapuje limit przesunięty o jedną turę albo niedziałający wcale: narzędzia byłyby wykonywane,
    choć model nie dostanie już tury, żeby skorzystać z wyniku, albo pętla nie miałaby końca."""
    route = route_after_agent(
        state_after(SEARCH, iterations),
        respond_tool_name = "respond_search",
        max_iterations    = MAX_ITERATIONS,
    )

    assert route == target


def test_tool_definitions_take_the_description_from_the_tool() -> None:
    """Sprawdza, czy definicja narzędzia dla modelu powstaje z samego narzędzia: opis to opis
    narzędzia z wpisanym limitem wywołań (tu 3), a schemat argumentów ma dokładnie pola `problem`
    i `symptoms`, bez notatki z kodu pisanej dla programisty.

    Wyłapuje definicję, która rozjechała się z narzędziem: model dostałby inny opis albo inne
    argumenty, niż narzędzie przyjmuje."""
    tool = FakeFindTicketsVectorTool()

    [definition] = tool_definitions([tool], ("find_tickets_vector",), {"find_tickets_vector": 3})

    assert definition.description == tool.description.replace(MAX_CALLS_PLACEHOLDER, "3")
    assert set(definition.parameters["properties"]) == {"problem", "symptoms"}
    assert "description" not in definition.parameters


def test_tool_definitions_put_the_call_limit_into_the_description() -> None:
    """Sprawdza, czy limit wywołań z konfiguracji (tu 7) jest wpisany w opis narzędzia, który czyta
    model, i czy w opisie nie zostaje żadne niewypełnione miejsce `{{…}}`.

    Wyłapuje opis bez limitu albo z gołym znacznikiem w jego miejscu: model ma znać limit z góry,
    a nie dowiadywać się o nim z błędu po przekroczeniu."""
    tool = FakeFindTicketsVectorTool()

    [definition] = tool_definitions([tool], ("find_tickets_vector",), {"find_tickets_vector": 7})

    assert "Limit wywołań w jednej sprawie: 7." in definition.description
    assert "{{" not in definition.description


def test_tool_definitions_refuse_a_tool_outside_the_list() -> None:
    """Sprawdza, czy podanie narzędzia, którego graf nie ma na liście dozwolonych (tu lista jest
    pusta), kończy się błędem przy składaniu definicji.

    Wyłapuje graf, który po cichu pokazałby modelowi narzędzie spoza swojej listy, na przykład
    bramkę z dostępem do bazy zgłoszeń, choć ma działać bez niej."""
    with pytest.raises(ValueError, match="spoza listy"):
        tool_definitions([FakeFindTicketsVectorTool()], (), {"find_tickets_vector": 3})


def test_tool_definitions_refuse_a_tool_without_a_call_limit() -> None:
    """Sprawdza, czy narzędzie, dla którego nie podano limitu wywołań, kończy się błędem przy
    składaniu definicji, a komunikat wskazuje ustawienie `AGENT_MAX_CALLS`.

    Wyłapuje narzędzie bez limitu: jego opis poszedłby do modelu z niewypełnionym miejscem na limit,
    a węzeł `run_tools` nie miałby czego egzekwować."""
    with pytest.raises(ValueError, match="AGENT_MAX_CALLS"):
        tool_definitions([FakeFindTicketsVectorTool()], ("find_tickets_vector",), {})
