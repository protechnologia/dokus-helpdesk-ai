from app.tools.tickets.find_tickets_text import FakeFindTicketsTextTool, FindTicketsTextQuery
from app.tools.tickets.find_tickets_text.models import MatchedTicket
from app.tools.tickets.find_tickets_vector import FakeFindTicketsVectorTool, FindTicketsVectorQuery
from app.tools.tickets.find_tickets_vector.fake import default_tickets as vector_tickets

QUERY = FindTicketsTextQuery(exact=["Nie udało się skomunikować z serwerem"])


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same id w tej samej kolejności: atrapa ma być przewidywalna."""
    tool = FakeFindTicketsTextTool()

    first  = await tool.search(QUERY)
    second = await tool.search(QUERY)

    assert [matched.ticket.ticket_id for matched in first.items]  == ["90011", "90012"]
    assert [matched.ticket.ticket_id for matched in second.items] == ["90011", "90012"]


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindTicketsTextTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_reads_the_same_records_as_from_the_vector_search() -> None:
    """Tekst dla modelu → rekordy z polami pod nazwami ze schematu, jak w `find_tickets_vector`;
    w miejscu podobieństwa stoi etykieta dopasowania."""
    tool = FakeFindTicketsTextTool()

    text = tool.render_for_model(await tool.search(QUERY))

    assert text.startswith("Znalezione zgłoszenia: 2 (pominięte ponad limit: 0)")
    assert "cause: Brak sekwencji numeracji na nowy rok" in text
    assert "[90011] 2026-03-02 · dopasowanie: dosłowny ciąg" in text
    assert "[90012] 2026-01-05 · dopasowanie: słowa"         in text
    assert "podobieństwo" not in text


async def test_cite_gives_sources_without_a_score() -> None:
    """Każde zgłoszenie z wyniku → jeden SourceRef z materiału „tickets" bez podobieństwa:
    dopasowanie dosłowne nie ma stopnia."""
    tool = FakeFindTicketsTextTool()

    refs = tool.cite(await tool.search(QUERY))

    assert [ref.item_id for ref in refs] == ["90011", "90012"]
    assert all(ref.source == "tickets" for ref in refs)
    assert all(ref.score is None for ref in refs)


async def test_a_ticket_found_both_ways_has_one_key() -> None:
    """To samo zgłoszenie z wyszukiwania wektorowego i tekstowego → ten sam klucz źródła, więc
    na liście źródeł odpowiedzi znajdzie się raz."""
    shared = vector_tickets()[0].ticket
    vector = FakeFindTicketsVectorTool()
    text   = FakeFindTicketsTextTool(tickets=[MatchedTicket(matched_by="words", ticket=shared)])

    vector_query = FindTicketsVectorQuery(problem="x", symptoms="y")

    vector_refs = vector.cite(await vector.search(vector_query))
    text_refs   = text.cite(await text.search(QUERY))

    assert text_refs[0].key == vector_refs[0].key
