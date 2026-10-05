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
from app.core_model.tickets.raw_ticket import RawTicket

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
    """Sprawdza, czy w zmyślonym zestawie zgłoszeń numery się nie powtarzają: ani wśród kart, ani
    wśród wątków.

    Wyłapuje dwa zgłoszenia o tym samym numerze: po numerze idzie odczyt i klucz źródła, więc
    jedno z nich przesłoniłoby drugie."""
    cards   = [card.ticket_id for card in default_cards()]
    threads = [row.ticket_id for row in default_threads()]

    assert len(cards)   == len(set(cards))
    assert len(threads) == len(set(threads))


def test_every_card_has_its_thread_but_not_every_thread_a_card() -> None:
    """Sprawdza, czy każda zmyślona karta ma swój wątek i czy dokładnie jedno zgłoszenie (`90011`)
    ma sam wątek, bez karty.

    Wyłapuje zestaw, który przestał przypominać prawdziwe bazy: tam wątek ma każde zgłoszenie,
    a kartę tylko to, które przeszło parsowanie i filtr jakości."""
    cards   = {card.ticket_id for card in default_cards()}
    threads = {row.ticket_id for row in default_threads()}

    assert cards < threads
    assert threads - cards == {"90011"}


def test_every_thread_names_its_own_ticket_and_subject() -> None:
    """Sprawdza, czy każdy zmyślony wątek zaczyna się od numeru i daty swojego zgłoszenia i czy
    temat zapisany w wierszu jest tym samym, który stoi w linii „Temat:" wątku.

    Wyłapuje wątek podpięty pod cudzy numer albo datę oraz temat w wierszu inny niż w wątku:
    z tego tematu bierze się tytuł źródła, więc atrapy podawałyby źródła z błędnym tytułem."""
    for row in default_threads():
        assert row.thread.startswith(f"ZGŁOSZENIE {row.ticket_id} z {row.ticket_date.isoformat()}")
        assert RawTicket.subject_of_thread(row.thread) == row.subject


async def test_whatever_a_search_fake_finds_the_thread_fake_can_read() -> None:
    """Sprawdza, czy każdy numer zgłoszenia, który oddają atrapy obu wyszukiwań, da się odczytać
    atrapą odczytu wątków: na każdy numer wraca wątek tego zgłoszenia.

    Wyłapuje numer znany atrapie wyszukiwania, a nieznany atrapie odczytu: graf na atrapach nie
    przeszedłby wtedy drogi od wyszukania zgłoszenia do źródła."""
    found = await _found_numbers()
    tool  = FakeReadTicketsThreadTool()

    threads = [await tool.search(ReadTicketsThreadQuery(ticket_id=number)) for number in found]

    assert [thread.ticket_id for thread in threads] == found


async def test_whatever_a_search_fake_finds_the_card_fake_answers_for() -> None:
    """Sprawdza, czy atrapa odczytu kart odpowiada na każdy numer z atrap obu wyszukiwań: kartą
    albo wpisem „bez karty", który dostaje tylko zgłoszenie `90011`.

    Wyłapuje numer, na który atrapa kart nie odpowiada wcale albo odpowiada błędem: brak karty
    to zwykły stan zgłoszenia, a nie usterka."""
    found  = await _found_numbers()
    result = await FakeReadTicketsCardTool().search(ReadTicketsCardQuery(ticket_ids=found))

    answered = sorted([*(card.ticket_id for card in result.cards), *result.without_card])

    assert answered            == found
    assert result.without_card == ["90011"]
