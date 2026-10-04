from app.agent_tools.tickets.fake_tickets import default_cards, default_threads
from app.agent_tools.tickets.find_tickets_text import FakeFindTicketsTextTool, FindTicketsTextQuery
from app.agent_tools.tickets.find_tickets_vector import (
    FakeFindTicketsVectorTool,
    FindTicketsVectorQuery,
)
from app.agent_tools.tickets.read_tickets_card import FakeReadTicketsCardTool, ReadTicketsCardQuery
from app.agent_tools.tickets.read_tickets_thread import (
    FakeReadTicketsThreadTool,
    ReadTicketsThreadQuery,
)
from app.core_model.ticket_raw import RawTicket

# Zmyślone zgłoszenia wspólne dla atrap czterech narzędzi: numer z atrapy wyszukiwania ma dać się
# odczytać atrapą odczytu, tak jak na produkcji.


async def _found_numbers() -> list[str]:
    """
    Description:
    Numery zgłoszeń, które oddają atrapy obu wyszukiwań, bez powtórzeń.

    Example args:
        (brak)

    Example result:
        ["90001", "90002", "90003", "90011", "90012"]
    """
    by_meaning = FindTicketsVectorQuery(problem="x", symptoms="y")
    by_wording = FindTicketsTextQuery(words="x")

    vector = await FakeFindTicketsVectorTool().find(by_meaning)
    text   = await FakeFindTicketsTextTool().find(by_wording)

    return sorted({found.ticket_id for found in [*vector.tickets, *text.tickets]})


def test_ticket_numbers_are_unique() -> None:
    """Numery kart i wątków → bez powtórzeń: po nich idzie odczyt i klucz źródła."""
    cards   = [card.ticket_id for card in default_cards()]
    threads = [row.ticket_id for row in default_threads()]

    assert len(cards)   == len(set(cards))
    assert len(threads) == len(set(threads))


def test_every_card_has_its_thread_but_not_every_thread_a_card() -> None:
    """Każda karta ma wątek, a jedno zgłoszenie ma sam wątek: tak jest w bazach — wątek ma każde
    zgłoszenie, kartę tylko to, które przeszło parsowanie i filtr jakości."""
    cards   = {card.ticket_id for card in default_cards()}
    threads = {row.ticket_id for row in default_threads()}

    assert cards < threads
    assert threads - cards == {"90011"}


def test_every_thread_names_its_own_ticket_and_subject() -> None:
    """Wątek → zaczyna się od numeru swojego zgłoszenia i niesie linię z tematem, który trafił
    do wiersza: z niej bierze się tytuł źródła."""
    for row in default_threads():
        assert row.thread.startswith(f"ZGŁOSZENIE {row.ticket_id} z {row.ticket_date.isoformat()}")
        assert RawTicket.subject_of_thread(row.thread) == row.subject


async def test_whatever_a_search_fake_finds_the_thread_fake_can_read() -> None:
    """Numery z atrap obu wyszukiwań → do odczytania atrapą wątków, wszystkie: graf na atrapach
    może przejść całą drogę od wyszukania do źródła."""
    found  = await _found_numbers()
    result = await FakeReadTicketsThreadTool().search(ReadTicketsThreadQuery(ticket_ids=found))

    assert [thread.ticket_id for thread in result.threads] == found


async def test_whatever_a_search_fake_finds_the_card_fake_answers_for() -> None:
    """Numery z atrap obu wyszukiwań → atrapa kart odpowiada na każdy: kartą albo wpisem „bez
    karty", nigdy błędem."""
    found  = await _found_numbers()
    result = await FakeReadTicketsCardTool().search(ReadTicketsCardQuery(ticket_ids=found))

    answered = sorted([*(card.ticket_id for card in result.cards), *result.without_card])

    assert answered            == found
    assert result.without_card == ["90011"]
