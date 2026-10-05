import httpx
import pytest

from app.agent_tools.tickets.fake_tickets import default_cards
from app.agent_tools.tickets.read_tickets_card import (
    FakeReadTicketsCardTool,
    ReadTicketsCardQuery,
    ReadTicketsCardTool,
)
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.db_qdrant import (
    DbQdrantConfigError,
    QdrantClient,
    TicketPoint,
    TicketsCollection,
    point_id_for,
)
from tests.helpers_transport import capturing, with_transport

# Narzędzie stoi na prawdziwej kolekcji i kliencie Qdranta, a podmieniony jest tylko transport —
# sprawdzamy więc to, co faktycznie idzie na drut, i jak odpowiedź staje się kartami.

CARDS = {card.ticket_id: card for card in default_cards()}

VECTOR = [0.1, 0.2, 0.3, 0.4]


def _stored(
    ticket_id: str,                 # np. "90001"
    payload:   dict | None = None,  # np. {"ticket_id": "90001"} — gdy test psuje payload
) -> dict:
    """
    Description:
    Punkt w kształcie, w jakim oddaje go odczyt Qdranta — zbudowany tak, jak zapisuje go
    indeksacja (`TicketPoint.from_ticket()`).

    Example args:
        ticket_id="90001"

    Example result:
        {"id": "…", "vector": {"problem": […], "sts": […]}, "payload": {"ticket_id": "90001", …}}
    """
    point = TicketPoint.from_ticket(CARDS[ticket_id], VECTOR, VECTOR).to_qdrant()

    if payload is not None:
        point["payload"] = payload

    return point


def _tool(
    stored: list[dict],          # np. [_stored("90001")]
    seen:   list | None = None,  # żądania do Qdranta, gdy test je sprawdza
) -> ReadTicketsCardTool:
    """
    Description:
    Buduje narzędzie na prawdziwej kolekcji z podmienionym transportem: Qdrant oddaje podane
    punkty.

    Example args:
        stored=[_stored("90001")]

    Example result:
        ReadTicketsCardTool odpowiadające jedną kartą, bez żadnej usługi
    """
    qdrant = with_transport(
        QdrantClient(base_url="http://qdrant:6333"),
        capturing(
            seen if seen is not None else [],
            {
                ("POST", "/collections/tickets/points"):
                    httpx.Response(200, json={"result": stored}),
            },
        ),
    )

    tool = ReadTicketsCardTool(
        tickets    = TicketsCollection(qdrant, "tickets", len(VECTOR)),
        resolution = get_resolution_classes(),
    )

    return tool


async def test_the_read_asks_for_the_points_of_the_given_numbers() -> None:
    """Numery zgłoszeń → na drucie identyfikatory punktów wyliczone z numerów, bez powtórzeń:
    narzędzie nie zna identyfikatorów Qdranta, liczy je kolekcja."""
    seen: list = []

    await _tool([], seen=seen).search(ReadTicketsCardQuery(ticket_ids=["90001", "90002", "90001"]))

    assert seen[0]["body"]["ids"] == [point_id_for("90001"), point_id_for("90002")]


async def test_a_point_comes_back_as_the_card_that_was_indexed() -> None:
    """Payload punktu → `ParsedTicket` ze wszystkimi polami, równy zaindeksowanemu: model ma
    dostać `cause` i `solution` jako pola, a `cite()` numer i datę samego zgłoszenia."""
    tool   = _tool([_stored("90001")])
    result = await tool.search(ReadTicketsCardQuery(ticket_ids=["90001"]))

    assert result.cards        == [CARDS["90001"]]
    assert result.without_card == []
    assert [ref.item_id for ref in tool.cite(result)] == ["90001"]


async def test_cards_follow_the_order_asked_not_the_order_stored() -> None:
    """Qdrant oddaje punkty w swojej kolejności → karty w kolejności numerów z zapytania."""
    tool   = _tool([_stored("90001"), _stored("90003")])
    result = await tool.search(ReadTicketsCardQuery(ticket_ids=["90003", "90001"]))

    assert [card.ticket_id for card in result.cards] == ["90003", "90001"]


async def test_a_ticket_without_a_point_is_listed_as_without_card() -> None:
    """Numer, którego w kolekcji nie ma → `without_card`, nie błąd: do kolekcji trafiają tylko
    zgłoszenia, które przeszły filtr jakości, a wątek ma każde."""
    tool   = _tool([_stored("90001")])
    result = await tool.search(ReadTicketsCardQuery(ticket_ids=["90011", "90001", "90019"]))

    assert [card.ticket_id for card in result.cards] == ["90001"]
    assert result.without_card                       == ["90011", "90019"]


async def test_a_payload_outside_the_contract_is_a_config_error_without_content() -> None:
    """Payload bez wymaganego pola → `DbQdrantConfigError` z numerem zgłoszenia i nazwą pola, ale
    bez treści: indeks z innej wersji kontraktu naprawia przebudowa, a treść zgłoszenia nie
    trafia do logów."""
    broken = dict(_stored("90001")["payload"])
    del broken["solution"]

    with pytest.raises(DbQdrantConfigError) as raised:
        await _tool([_stored("90001", payload=broken)]).search(
            ReadTicketsCardQuery(ticket_ids=["90001"])
        )

    message = str(raised.value)

    assert "'90001'" in message
    assert "solution" in message
    assert "tickets reindex" in message
    assert broken["problem"] not in message
    assert raised.value.__cause__ is None


def test_the_tool_and_its_fake_describe_themselves_the_same() -> None:
    """Ten sam słownik w narzędziu i w atrapie → ten sam opis dla modelu, z klasami
    rozstrzygnięcia: test grafu na atrapie sprawdza opis, który model dostanie na produkcji."""
    vocabulary = get_resolution_classes()

    assert _tool([]).description == FakeReadTicketsCardTool(resolution=vocabulary).description


async def test_aclose_closes_the_qdrant_client() -> None:
    """`aclose()` → zamknięte połączenie Qdranta: sprzątający nie musi wiedzieć, z czego
    narzędzie jest zbudowane."""
    tool = _tool([])

    await tool.aclose()

    assert tool._tickets._client._client.is_closed
