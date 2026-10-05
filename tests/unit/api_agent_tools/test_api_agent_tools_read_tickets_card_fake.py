import json
from datetime import date

from app.agent_tools.tickets.read_tickets_card import FakeReadTicketsCardTool, ReadTicketsCardQuery

QUERY = ReadTicketsCardQuery(ticket_ids=["90002", "90011", "90001"])


async def test_cards_come_back_in_the_order_asked() -> None:
    """Sprawdza, czy atrapa oddaje karty w kolejności numerów z zapytania: dla numerów 90002, 90011
    i 90001 wracają karty 90002 i 90001, a numer 90011, który karty nie ma, stoi osobno.

    Wyłapuje atrapę, która układa karty po swojemu albo gubi numer bez karty, czyli odpowiada
    inaczej niż prawdziwy odczyt, który zastępuje w testach."""
    result = await FakeReadTicketsCardTool().search(QUERY)

    assert [card.ticket_id for card in result.cards] == ["90002", "90001"]
    assert result.without_card                       == ["90011"]


async def test_a_number_asked_twice_is_read_once() -> None:
    """Sprawdza, czy numer podany w zapytaniu dwa razy jest w wyniku raz: dla numerów 90001, 90001,
    90011 i 90011 wraca jedna karta i jeden numer bez karty.

    Wyłapuje powtórzenia w wyniku: model dostałby ten sam rekord dwukrotnie."""
    query  = ReadTicketsCardQuery(ticket_ids=["90001", "90001", "90011", "90011"])
    result = await FakeReadTicketsCardTool().search(query)

    assert [card.ticket_id for card in result.cards] == ["90001"]
    assert result.without_card                       == ["90011"]


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy po odczycie zapytanie jest zapisane na liście `queries` atrapy.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie miałby jak sprawdzić, które karty
    agent przeczytał."""
    tool = FakeReadTicketsCardTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_every_card_field_under_its_schema_name() -> None:
    """Sprawdza, czy tekst dla modelu to JSON, w którym karta ma wszystkie dziesięć pól pod nazwami
    ze schematu (między innymi `cause`, `solution`, `questions_summary`), z datą zapisaną jako
    `2026-04-22`, a numer bez karty stoi w `without_card`.

    Wyłapuje pole zgubione albo nazwane inaczej po drodze do modelu: prompty grafów odwołują się do
    pól karty po nazwie, więc model nie znalazłby tego, o czym prompt mówi."""
    tool = FakeReadTicketsCardTool()
    body = json.loads(tool.render_for_model(await tool.search(QUERY)))

    card = body["cards"][0]

    assert set(card) == {
        "ticket_id",
        "date",
        "component",
        "problem",
        "symptoms",
        "error_codes",
        "cause",
        "solution",
        "resolution",
        "questions_summary",
    }
    assert card["ticket_id"] == "90002"
    assert card["date"]      == "2026-04-22"
    assert card["cause"]     == "Plik blokady pozostawiony po aktualizacji blokował pobieranie"
    assert body["without_card"] == ["90011"]


async def test_the_model_does_not_see_artifact_metadata() -> None:
    """Sprawdza, czy w tekście dla modelu nie ma wersji słownika rozstrzygnięć
    (`resolution_vocabulary_version`).

    Wyłapuje przeciek metadanych artefaktu do modelu: to informacja dla nas, nie treść zgłoszenia,
    a model potraktowałby ją jak fakt o sprawie."""
    tool = FakeReadTicketsCardTool()
    text = tool.render_for_model(await tool.search(QUERY))

    assert "resolution_vocabulary_version" not in text


async def test_the_three_default_cards_share_a_symptom_and_differ_in_cause() -> None:
    """Sprawdza, czy trzy karty z wbudowanego zestawu atrapy (90001, 90002, 90003) mają ten sam
    `problem` i trzy różne przyczyny.

    Wyłapuje zmianę zestawu, po której karty przestają być jednym objawem o kilku przyczynach: to
    najczęstszy kształt trafień w korpusie, na którym agent ma przeczytać wszystkie karty, zamiast
    poprzestać na pierwszej."""
    query  = ReadTicketsCardQuery(ticket_ids=["90001", "90002", "90003"])
    result = await FakeReadTicketsCardTool().search(query)

    assert len({card.problem for card in result.cards}) == 1
    assert len({card.cause for card in result.cards})   == 3


async def test_cite_gives_one_source_per_card_read() -> None:
    """Sprawdza, czy lista źródeł ma jeden wpis na każdą odczytaną kartę: dla kart 90002 i 90001 dwa
    wpisy z materiału „tickets", z `problem` karty jako tytułem i z datą zgłoszenia. Numeru 90011,
    który karty nie ma, na liście nie ma.

    Wyłapuje źródło przypisane zgłoszeniu, którego karty model nie dostał, oraz wpis, w którym tytuł
    albo data nie pochodzą z karty."""
    tool   = FakeReadTicketsCardTool()
    result = await tool.search(QUERY)

    refs = tool.cite(result)

    assert [ref.item_id for ref in refs] == ["90002", "90001"]
    assert all(ref.source == "tickets" for ref in refs)
    assert refs[0].title == "Nie przychodzą przesyłki z e-Doręczeń"
    assert refs[0].date  == date(2026, 4, 22)


async def test_reading_only_tickets_without_cards_cites_nothing() -> None:
    """Sprawdza, czy odczyt samego numeru bez karty (90011) daje pusty wynik i pustą listę źródeł.

    Wyłapuje źródło powstające z niczego: graf wymagający źródeł przepuściłby wtedy propozycję,
    która nie opiera się na żadnym przeczytanym materiale."""
    tool   = FakeReadTicketsCardTool()
    result = await tool.search(ReadTicketsCardQuery(ticket_ids=["90011"]))

    assert result.cards      == []
    assert tool.cite(result) == []
