from app.agent_tools.tickets.find_tickets_text import FakeFindTicketsTextTool, FindTicketsTextQuery
from app.agent_tools.tickets.find_tickets_text.models import MatchedTicket
from app.agent_tools.tickets.find_tickets_vector import (
    FakeFindTicketsVectorTool,
    FindTicketsVectorQuery,
)
from app.agent_tools.tickets.find_tickets_vector.fake import default_tickets as vector_tickets

QUERY = FindTicketsTextQuery(exact=["Nie udało się skomunikować z serwerem"])


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same id w tej samej kolejności: atrapa ma być przewidywalna."""
    tool = FakeFindTicketsTextTool()

    first  = await tool.search(QUERY)
    second = await tool.search(QUERY)

    assert [matched.ticket_id for matched in first.items]  == ["90011", "90012"]
    assert [matched.ticket_id for matched in second.items] == ["90011", "90012"]


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindTicketsTextTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_reads_original_threads_not_cards() -> None:
    """Tekst dla modelu → nagłówek z licznikami i wątki z etykietą dopasowania; pól karty nie ma,
    bo baza tekstowa trzyma oryginały."""
    tool = FakeFindTicketsTextTool()

    text = tool.render_for_model(await tool.search(QUERY))

    assert text.startswith("Znalezione zgłoszenia: 2 (pominięte ponad limit: 0)")
    assert "[90011] 2026-03-02 · dopasowanie: dosłowny ciąg" in text
    assert "[90012] 2026-01-05 · dopasowanie: słowa"         in text
    assert "Brakowało sekwencji numeracji na 2026 rok" in text
    assert "cause:" not in text and "podobieństwo" not in text


async def test_every_thread_stands_between_its_own_markers() -> None:
    """Tekst dla modelu → wątek każdego zgłoszenia między liniami z jego numerem, w kształcie
    `RawTicket.as_thread()`: wątek ma własne puste linie, więc bez ogranicznika zlałby się
    z następnym."""
    tool = FakeFindTicketsTextTool()

    text = tool.render_for_model(await tool.search(QUERY))

    start, end = text.index("--- wątek 90011 ---"), text.index("--- koniec wątku 90011 ---")

    assert text.index("[90011] 2026-03-02") < start < end < text.index("[90012] 2026-01-05")
    assert "ZGŁOSZENIE 90011 z 2026-03-02\nTemat: Błąd przy podpisie" in text[start:end]
    assert "ok. 40 MB" in text[start:end]


async def test_cite_gives_sources_titled_by_subject_without_a_score() -> None:
    """Każde zgłoszenie z wyniku → jeden SourceRef z materiału „tickets", z tematem jako tytułem
    i bez podobieństwa: dopasowanie dosłowne nie ma stopnia."""
    tool = FakeFindTicketsTextTool()

    refs = tool.cite(await tool.search(QUERY))

    assert [ref.item_id for ref in refs] == ["90011", "90012"]
    assert [ref.title for ref in refs]   == ["Błąd przy podpisie", "Nie da się zapisać pisma"]
    assert all(ref.source == "tickets" for ref in refs)
    assert all(ref.score is None for ref in refs)


async def test_a_ticket_found_both_ways_has_one_key() -> None:
    """To samo zgłoszenie z wyszukiwania wektorowego (karta) i tekstowego (wątek) → ten sam klucz
    źródła, więc na liście źródeł odpowiedzi znajdzie się raz."""
    shared = vector_tickets()[0].ticket
    found  = MatchedTicket(
        matched_by = "words",
        ticket_id  = shared.ticket_id,
        date       = shared.date,
        subject    = "Brak przesyłek",
        thread     = "ZGŁOSZENIE 90001 z 2026-02-10\nTemat: Brak przesyłek\n\nOPIS…",
    )
    vector = FakeFindTicketsVectorTool()
    text   = FakeFindTicketsTextTool(tickets=[found])

    vector_query = FindTicketsVectorQuery(problem="x", symptoms="y")

    vector_refs = vector.cite(await vector.search(vector_query))
    text_refs   = text.cite(await text.search(QUERY))

    assert text_refs[0].key == vector_refs[0].key
