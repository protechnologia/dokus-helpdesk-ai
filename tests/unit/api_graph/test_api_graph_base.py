from pathlib import Path

import pytest

from app.graph import GraphState, merge_sources, route_after_agent, tool_definitions
from app.llm import ChatMessage
from app.nodes.agent import tool_call_turn
from app.tools import SourceRef
from app.tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool


def make_ref(
    item_id: str = "90001",  # np. "90002"
) -> SourceRef:
    """
    Description:
    Buduje źródło z `find_tickets_vector`, różniące się tylko id.

    Example args:
        item_id="90001"

    Example result:
        SourceRef(source="tickets", item_id="90001", title="Brak przesyłek", score=0.9)
    """
    return SourceRef(source="tickets", item_id=item_id, title="Brak przesyłek", score=0.9)


def test_merge_sources_skips_what_is_already_there() -> None:
    """Drugie trafienie tego samego zgłoszenia → na liście raz, z pierwszego trafienia; nowe
    źródła dochodzą na koniec, w kolejności."""
    current = [make_ref("90001")]
    new     = [make_ref("90001"), make_ref("90002")]

    assert [ref.item_id for ref in merge_sources(current, new)] == ["90001", "90002"]


def test_merge_sources_keeps_the_same_id_from_another_tool() -> None:
    """To samo id z innego narzędzia → osobne źródło: klucz to `source:item_id`, nie samo id."""
    ticket   = make_ref("33644")
    fragment = SourceRef(source="docs", item_id="33644", title="Instrukcja 4.12", score=0.7)

    assert len(merge_sources([ticket], [fragment])) == 2


SEARCH  = tool_call_turn("find_tickets_vector", {"problem": "Brak przesyłek", "symptoms": "pusto"})
RESPOND = tool_call_turn("respond_search", {}, call_id="call_2")
TEXT    = ChatMessage(role="assistant", content="Najpierw sprawdzę…")
BOTH    = ChatMessage(role="assistant", tool_calls=[*SEARCH.tool_calls, *RESPOND.tool_calls])


def state_after(
    turn: ChatMessage,  # np. tool_call_turn("find_tickets_vector", {…})
) -> GraphState:
    """
    Description:
    Stan grafu, którego ostatnia wiadomość to podana tura modelu.

    Example args:
        turn=tool_call_turn("find_tickets_vector", {…})

    Example result:
        GraphState(input_text="x", messages=[ChatMessage(role="assistant", …)])
    """
    return GraphState(input_text="x", messages=[turn])


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
    """Tura modelu → narzędzie wiedzy wraca do `run_tools`; odpowiedź, sam tekst i odpowiedź
    z innym narzędziem idą do `respond`, który rozstrzyga błędy formatu (p. 11)."""
    assert route_after_agent(state_after(turn), respond_tool_name="respond_search") == target


def test_tool_definitions_take_the_description_from_the_graph(tmp_path: Path) -> None:
    """Narzędzie z listy dozwolonych → opis z `<graf>/<nazwa>.md` bez komentarzy redakcyjnych,
    schemat zapytania bez docstringów."""
    description = tmp_path / "find_tickets_vector.md"
    description.write_text("<!-- notatka -->\nSzuka zgłoszeń.\n", encoding="utf-8")

    tools = [FakeFindTicketsVectorTool()]

    [definition] = tool_definitions(tools, ("find_tickets_vector",), tmp_path)

    assert definition.description                  == "Szuka zgłoszeń."
    assert set(definition.parameters["properties"]) == {"problem", "symptoms"}
    assert "description" not in definition.parameters


def test_tool_definitions_refuse_a_tool_outside_the_list(tmp_path: Path) -> None:
    """Narzędzie spoza listy dozwolonych grafu → błąd składania, nie definicja dla modelu."""
    with pytest.raises(ValueError):
        tool_definitions([FakeFindTicketsVectorTool()], (), tmp_path)
