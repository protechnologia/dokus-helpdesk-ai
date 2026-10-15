"""
Description:
Spójność zestawu scenariuszy rozwiązania (`data/safe/golden/solution.json`) bez modelu: czy sprawy
dotyczą grafu z narzędziami wiedzy i treścią dla klienta, czy zmiany kart trafiają we wbudowane
karty atrap i czy fakty, które treść ma nieść, naprawdę stoją w materiale sprawy, a nie
w zgłoszeniu. Test na żywym modelu z takim zestawem mierzyłby co innego, niż obiecuje, więc te
warunki pilnuje się w domyślnym `pytest`.

| warunek                                        | czym grozi jego brak                          |
|------------------------------------------------|-----------------------------------------------|
| sekcja nazywa graf z narzędziami wiedzy        | sekcja, której nikt nie uruchomi, albo graf,  |
| i polem `text`                                 | którego treści dla klienta nie da się ocenić  |
| sprawy mają różne identyfikatory, sekcja ma    | dwie sprawy o jednym identyfikatorze, zestaw  |
| fakty wymagane i wzmiankę niepożądaną          | bez warunku albo bez licznika                 |
| zgłoszenie ma kształt wątku                    | sprawa, która nie wygląda jak wejście trasy   |
| zmiany kart nazywają wbudowane karty i ich     | zmiana, która nie trafia w żadną kartę, więc  |
| pola                                           | model czyta materiał bez niej                 |
| fakt wymagany stoi w kartach sprawy, nie stoi  | warunek nie do spełnienia albo spełniony      |
| w zgłoszeniu                                   | przepisaniem zgłoszenia                       |
| wzmianka oczekiwana stoi w kartach sprawy      | licznik zawsze pusty                          |
| sprawa ze zmienionymi kartami ma parę bez      | brak porównania: nie wiadomo, czy fakt        |
| zmian, o tym samym temacie                     | przyszedł z karty                             |
| narzędzia sprawy to narzędzia grafu, a odczyt  | sprawa na wbudowanych kartach, w której       |
| kart oddaje karty sprawy                       | zmiana nigdy nie dociera do modelu            |
"""

import asyncio

import pytest

from app.agent_tools.tickets.fake_tickets import default_cards
from app.agent_tools.tickets.read_tickets_card.models import ReadTicketsCardQuery
from app.core_model.tickets.parsed_ticket import ParsedTicket
from tests._helpers.graphs import graph_module, graph_names, has_sources, output_fields
from tests._helpers.scenarios.solution import (
    SolutionCase,
    cards_text,
    case_cards,
    case_tools,
    mentions,
    mentions_all,
    solution_sections,
    ticket_subject,
)

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = solution_sections()

# Pary (graf, sprawa) zestawu, czytane przy imporcie: z nich powstają parametry testów, nazwane
# identyfikatorem sprawy. Obok podzbiory spraw, których dotyczy tylko część testów.
CASES = [
    pytest.param(graph, case, id=case.case_id)
    for graph, section in SECTIONS.items()
    for case in section.cases
]
CHANGED_CASES  = [param for param in CASES if param.values[1].card_changes]
REQUIRED_CASES = [param for param in CASES if param.values[1].must_mention]
EXPECTED_CASES = [param for param in CASES if param.values[1].should_mention]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph_with_knowledge_tools_and_a_client_text(graph: str) -> None:
    """Sprawdza, czy każda sekcja nazywa się jak katalog grafu, który ma narzędzia wiedzy (listę
    źródeł w stanie) i treść dla klienta w polu `text` wyniku.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i graf
    bez treści dla klienta: warunek faktów w treści nie miałby czego sprawdzać."""
    assert graph in graph_names()

    module = graph_module(graph)

    assert has_sources(module)
    assert "text" in output_fields(module)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_section_has_unique_ids_required_facts_and_an_unwanted_mention(graph: str) -> None:
    """Sprawdza, czy identyfikatory spraw w sekcji się nie powtarzają, a sekcja ma sprawę
    z faktami wymaganymi i sprawę z wzmianką niepożądaną.

    Wyłapuje dwie sprawy o jednym identyfikatorze w raporcie i zestaw, w którym zniknął warunek
    testu albo licznik kroku, który klient już wykonał."""
    cases = SECTIONS[graph].cases
    ids   = [case.case_id for case in cases]

    assert len(ids) == len(set(ids))
    assert any(case.must_mention for case in cases)
    assert any(case.should_not_mention for case in cases)


@pytest.mark.parametrize(("graph", "case"), CASES)
def test_every_case_is_a_ticket_with_a_thread(graph: str, case: SolutionCase) -> None:
    """Sprawdza, czy każda sprawa ma kształt wątku z `RawTicket.as_thread()`: nagłówek zgłoszenia,
    temat i opis zgłaszającego.

    Wyłapuje sprawę, która nie wygląda jak wejście trasy `/suggest`: model dostałby inny kształt
    niż na produkcji, a wynik nie mówiłby nic o prawdziwej sprawie."""
    assert case.text.startswith("ZGŁOSZENIE ")
    assert "\nTemat: " in case.text
    assert "\nOPIS ZGŁASZAJĄCEGO:\n" in case.text


@pytest.mark.parametrize(("graph", "case"), CHANGED_CASES)
def test_card_changes_name_built_in_cards_and_their_fields(graph: str, case: SolutionCase) -> None:
    """Sprawdza, czy zmiany kart nazywają karty wbudowanego materiału atrap i pola karty, a karty
    sprawy dają się zbudować.

    Wyłapuje zmianę z literówką w numerze karty albo w nazwie pola: sprawa szłaby na materiale
    bez zmiany, a warunek faktu z karty nie miałby skąd przyjść."""
    numbers = {card.ticket_id for card in default_cards()}

    fields  = set(ParsedTicket.model_fields)

    assert set(case.card_changes) <= numbers
    assert all(set(changes) <= fields for changes in case.card_changes.values())
    assert case_cards(case)


@pytest.mark.parametrize(("graph", "case"), REQUIRED_CASES)
def test_a_required_fact_stands_in_the_cards_and_not_in_the_ticket(
    graph: str,
    case:  SolutionCase,
) -> None:
    """Sprawdza, czy każdy fakt wymagany w treści dla klienta stoi w kartach sprawy, a nie stoi
    w zgłoszeniu.

    Wyłapuje warunek nie do spełnienia — faktu nie ma w materiale, więc model nie ma go skąd
    wziąć — i warunek spełniany przepisaniem zgłoszenia, który niczego o karcie nie mówi."""
    cards = cards_text(case)

    assert all(mentions(cards, fact) for fact in case.must_mention)
    assert not any(mentions(case.text, fact) for fact in case.must_mention)


@pytest.mark.parametrize(("graph", "case"), EXPECTED_CASES)
def test_an_expected_mention_stands_in_the_cards(graph: str, case: SolutionCase) -> None:
    """Sprawdza, czy wzmianka oczekiwana stoi w kartach sprawy: wszystkie jej fakty naraz.

    Wyłapuje licznik zawsze pusty: wzmianki, której w materiale nie ma, model nie napisze, więc
    para nie pokazałaby, że krok pada bez wątku."""
    assert mentions_all(cards_text(case), case.should_mention)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_case_with_changed_cards_has_a_pair_without_changes(graph: str) -> None:
    """Sprawdza, czy każda sprawa ze zmienionymi kartami ma w sekcji parę o tym samym temacie
    zgłoszenia, bez zmian kart.

    Wyłapuje sprawę bez porównania: nie dałoby się powiedzieć, czy ostrzeżenie przyszło z karty,
    czy model dopisuje je zawsze."""
    cases = SECTIONS[graph].cases

    for changed in (case for case in cases if case.card_changes):
        assert any(
            ticket_subject(case.text) == ticket_subject(changed.text) and not case.card_changes
            for case in cases
        ), changed.case_id


@pytest.mark.parametrize(("graph", "case"), CASES)
def test_case_tools_are_the_graph_tools_and_read_the_case_cards(
    graph: str,
    case:  SolutionCase,
) -> None:
    """Sprawdza, czy narzędzia sprawy to wszystkie narzędzia grafu w kolejności `TOOL_NAMES`,
    a odczyt kart oddaje karty sprawy, ze zmianami, gdy sprawa je ma.

    Wyłapuje sprawę, w której zmiana karty nie dociera do odczytu: model czytałby wbudowaną kartę,
    a warunek faktu z karty sprawdzałby coś, czego model nie widział."""
    tools  = case_tools(case)
    reader = next(tool for tool in tools if tool.name == "read_tickets_card")
    wanted = [card.ticket_id for card in default_cards()]
    read   = asyncio.run(reader.search(ReadTicketsCardQuery(ticket_ids=wanted)))

    assert [tool.name for tool in tools] == list(graph_module(graph).TOOL_NAMES)
    assert read.cards == case_cards(case)
