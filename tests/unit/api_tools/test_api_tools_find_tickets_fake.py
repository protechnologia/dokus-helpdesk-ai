from app.tools.find_tickets import FakeFindTickets, FindTicketsQuery

QUERY = FindTicketsQuery(problem="Nie przychodzą przesyłki", symptoms="pusta skrzynka odbiorcza")


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same id w tej samej kolejności: atrapa ma być przewidywalna, żeby
    test grafu nie zależał od tego, którym z kolei wywołaniem jest."""
    tool = FakeFindTickets()

    first  = await tool.search(QUERY)
    second = await tool.search(QUERY)

    assert [found.ticket.ticket_id for found in first.items] == ["90001", "90002", "90003"]
    assert [found.ticket.ticket_id for found in second.items] == ["90001", "90002", "90003"]


async def test_the_default_set_has_one_symptom_and_distinct_causes() -> None:
    """Zestaw wbudowany → jeden objaw, różne przyczyny: najczęstszy kształt trafień w korpusie,
    na którym agent ma dopytywać zamiast zgadywać."""
    result = await FakeFindTickets().search(QUERY)

    assert len({found.ticket.problem for found in result.items}) == 1
    assert len({found.ticket.cause   for found in result.items}) == 3


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindTickets()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_cite_gives_one_source_per_ticket_shown() -> None:
    """Każde zgłoszenie z wyniku → jeden SourceRef z id, tytułem i datą zgłoszenia, a jego id
    widać w tekście dla modelu: cytować wolno tylko to, co model zobaczył."""
    tool   = FakeFindTickets()
    result = await tool.search(QUERY)

    refs = tool.cite(result)
    text = tool.render_for_model(result)

    assert [ref.item_id for ref in refs] == ["90001", "90002", "90003"]
    assert all(ref.source == "find_tickets" for ref in refs)
    assert refs[0].title == "Nie przychodzą przesyłki z e-Doręczeń"
    assert refs[0].date.isoformat() == "2026-02-10"
    assert all(f"[{ref.item_id}]" in text for ref in refs)


async def test_an_empty_result_says_what_the_threshold_cut() -> None:
    """Brak zgłoszeń i trzy odcięte → tekst mówi o obu, a lista źródeł jest pusta: „nic nie
    było" i „próg to wyciął" to dla agenta różne sytuacje."""
    tool   = FakeFindTickets(tickets=[], dropped_below_threshold=3)
    result = await tool.search(QUERY)

    assert tool.cite(result) == []
    assert "Znalezione zgłoszenia: 0 (odcięte progiem: 3)" in tool.render_for_model(result)
