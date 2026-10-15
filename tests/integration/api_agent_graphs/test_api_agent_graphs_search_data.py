"""
Description:
Spójność zestawu scenariuszy rozpoznania (`data/safe/golden/search.json`) bez modelu: czy sprawy
dotyczą grafu z narzędziami kodu, czy para „komunikat w kodzie / komunikatu nigdzie” naprawdę
stoi na paczce syntetycznej i czy narzędzia sprawy to atrapy zgłoszeń i instrukcji z prawdziwym
kodem. Test na żywym modelu z takim zestawem mierzyłby co innego, niż obiecuje, więc te warunki
pilnuje się w domyślnym `pytest`.

| warunek                                       | czym grozi jego brak                         |
|-----------------------------------------------|----------------------------------------------|
| sekcja nazywa graf z cytowaniem kodu          | sekcja, której nikt nie uruchomi, albo graf, |
| i listą źródeł                                | który przyczyny z kodu nie wskaże            |
| sprawy mają różne identyfikatory, a sekcja    | zestaw mierzący jedną stronę pary            |
| ma sprawę z wymaganą przyczyną i bez niej     |                                              |
| zgłoszenie ma kształt wątku                   | sprawa, która nie wygląda jak wejście trasy  |
| wymagany plik przyczyny leży w paczce, a      | wymóg pliku, którego nie ma albo w którym    |
| cytowany komunikat stoi w nim                 | komunikatu nie ma                            |
| komunikatu sprawy „nigdzie” nie ma w paczce   | sprawa, w której cytowanie przyczyny jest    |
|                                               | słuszne, a test je karze                     |
| fragment wykluczony przez wątek leży w paczce | licznik, który nic nie liczy                 |
| nazwa do wymienienia stoi w paczce, nie stoi  | licznik zawsze pełny albo zawsze pusty       |
| w zgłoszeniu                                  |                                              |
| narzędzia sprawy: atrapy i prawdziwy kod      | sprawa „nigdzie” na atrapie szukania, która  |
|                                               | zawsze coś znajduje                          |
| szukanie zgłoszeń znajduje coś tylko w sprawie | przyczyna z historycznej sprawy w sprawie,   |
| z `finds_tickets_and_docs`, a nigdy w sprawie | która ma mierzyć kod                         |
| z komunikatem z ekranu                        |                                              |
"""

import asyncio

import pytest

from app.agent_tools.tickets.find_tickets_vector.models import FindTicketsVectorQuery
from tests._helpers.graphs import graph_module, graph_names, has_sources
from tests._helpers.scenarios.search import (
    QUOTE_TOOL,
    SearchCase,
    case_tools,
    quoted_messages,
    search_sections,
)
from tests._helpers.synthetic_code import synthetic_code_texts, synthetic_code_tools

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = search_sections()

# Pary (graf, sprawa) zestawu, czytane przy imporcie: z nich powstają parametry testów, nazwane
# identyfikatorem sprawy. Obok podzbiory spraw, których dotyczy tylko część testów.
CASES = [
    pytest.param(graph, case, id=case.case_id)
    for graph, section in SECTIONS.items()
    for case in section.cases
]
CAUSE_CASES    = [param for param in CASES if param.values[1].must_quote_as_cause]
NOWHERE_CASES  = [param for param in CASES if param.values[1].must_not_quote_any_cause]
EXCLUDED_CASES = [param for param in CASES if param.values[1].should_not_quote_as_cause]
NOTES_CASES    = [param for param in CASES if param.values[1].notes_should_include]
MESSAGE_CASES  = [param for param in CASES if quoted_messages(param.values[1].text)]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph_that_quotes_code(graph: str) -> None:
    """Sprawdza, czy każda sekcja nazywa się jak katalog grafu, który daje modelowi cytowanie kodu
    i ma w stanie listę źródeł.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i sekcję
    grafu bez cytowania kodu: wymóg pliku przyczyny nie miałby czego sprawdzać."""
    assert graph in graph_names()

    module = graph_module(graph)

    assert QUOTE_TOOL in module.TOOL_NAMES
    assert has_sources(module)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_section_has_both_sides_of_the_pair_and_unique_ids(graph: str) -> None:
    """Sprawdza, czy sekcja ma sprawę, która wymaga pliku przyczyny, i sprawę, która nie dopuszcza
    żadnej przyczyny z kodu, a identyfikatory spraw się nie powtarzają.

    Wyłapuje zestaw mierzący jedną stronę: model, który cytuje przyczynę zawsze albo nigdy,
    przeszedłby test drugiej strony bez żadnego sprawdzenia; sprawę, która jednocześnie wymaga
    pliku przyczyny i zakazuje każdej przyczyny, więc nie może przejść; i dwie sprawy o jednym
    identyfikatorze w raporcie."""
    cases = SECTIONS[graph].cases
    ids   = [case.case_id for case in cases]

    assert any(case.must_quote_as_cause for case in cases)
    assert any(case.must_not_quote_any_cause for case in cases)
    assert not any(case.must_quote_as_cause and case.must_not_quote_any_cause for case in cases)
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(("graph", "case"), CASES)
def test_every_case_is_a_ticket_with_a_thread(graph: str, case: SearchCase) -> None:
    """Sprawdza, czy każda sprawa ma kształt wątku z `RawTicket.as_thread()`: nagłówek zgłoszenia,
    temat i opis zgłaszającego.

    Wyłapuje sprawę, która nie wygląda jak wejście trasy `/search`: model dostałby inny kształt
    niż na produkcji, a wynik nie mówiłby nic o prawdziwej sprawie."""
    assert case.text.startswith("ZGŁOSZENIE ")
    assert "\nTemat: " in case.text
    assert "\nOPIS ZGŁASZAJĄCEGO:\n" in case.text


@pytest.mark.parametrize(("graph", "case"), CAUSE_CASES)
def test_a_required_cause_file_lies_in_the_package_and_carries_the_message(
    graph: str,
    case:  SearchCase,
) -> None:
    """Sprawdza, czy każdy plik, który sprawa wymaga wśród cytowań przyczyny, leży w paczce
    syntetycznej, a komunikat z ekranu — gdy zgłoszenie go cytuje — stoi dosłownie w jednym
    z tych plików.

    Wyłapuje wymóg pliku spoza paczki albo pliku, w którym komunikatu nie ma: model, który znalazł
    komunikat i zacytował właściwe miejsce, wychodziłby na błędny, a wymóg pliku spoza paczki nie
    dałby się spełnić wcale."""
    texts    = synthetic_code_texts()
    messages = quoted_messages(case.text)
    required = case.must_quote_as_cause

    assert all(path in texts for path in required)
    assert all(any(message in texts[path] for path in required) for message in messages)


@pytest.mark.parametrize(("graph", "case"), NOWHERE_CASES)
def test_the_message_of_a_case_without_a_cause_stands_nowhere(
    graph: str,
    case:  SearchCase,
) -> None:
    """Sprawdza, czy sprawa, która nie dopuszcza przyczyny z kodu, cytuje komunikat z ekranu i czy
    tego komunikatu nie ma w żadnym pliku paczki syntetycznej.

    Wyłapuje sprawę „nigdzie”, w której komunikat jednak stoi w kodzie: model, który go znalazł
    i słusznie zacytował miejsce, wychodziłby na cytującego przyczynę z luźnego pliku."""
    messages = quoted_messages(case.text)
    texts    = synthetic_code_texts().values()

    assert messages
    assert not any(message in text for text in texts for message in messages)


@pytest.mark.parametrize(("graph", "case"), EXCLUDED_CASES)
def test_a_fragment_not_to_quote_lies_in_the_package(graph: str, case: SearchCase) -> None:
    """Sprawdza, czy fragment, który wątek wyklucza jako przyczynę, wskazuje plik paczki
    syntetycznej i zakres linii, który w tym pliku istnieje.

    Wyłapuje licznik, który nic nie liczy: fragment spoza paczki albo za końcem pliku nie nakryje
    się z żadnym cytowaniem, więc raport zawsze mówiłby „nie”."""
    fragment = case.should_not_quote_as_cause
    texts    = synthetic_code_texts()

    assert fragment is not None
    assert fragment.path in texts
    assert 1 <= fragment.from_line <= fragment.to_line <= len(texts[fragment.path].split("\n"))


@pytest.mark.parametrize(("graph", "case"), NOTES_CASES)
def test_a_name_to_mention_stands_in_the_package_and_not_in_the_ticket(
    graph: str,
    case:  SearchCase,
) -> None:
    """Sprawdza, czy każda nazwa, którą uwagi mają wymienić, stoi w którejś ścieżce paczki
    syntetycznej, a nie stoi w zgłoszeniu.

    Wyłapuje licznik zawsze pełny — model przepisałby nazwę ze zgłoszenia, nie znajdując jej
    w kodzie — i zawsze pusty, gdy nazwy nie ma w paczce."""
    paths = list(synthetic_code_texts())

    assert all(any(name in path for path in paths) for name in case.notes_should_include)
    assert not any(name.casefold() in case.text.casefold() for name in case.notes_should_include)


@pytest.mark.parametrize(("graph", "case"), CASES)
def test_case_tools_are_the_graph_tools_with_real_code(graph: str, case: SearchCase) -> None:
    """Sprawdza, czy narzędzia sprawy to wszystkie narzędzia grafu w kolejności `TOOL_NAMES`,
    z prawdziwymi narzędziami kodu i atrapami zgłoszeń i instrukcji.

    Wyłapuje sprawę na atrapie szukania w kodzie, która zawsze oddaje te same linie — para
    „nigdzie” nie mierzyłaby wtedy niczego — i narzędzie grafu, którego sprawa nie dostała."""
    tools = case_tools(case)
    code  = {tool.name for tool in synthetic_code_tools()}

    assert [tool.name for tool in tools] == list(graph_module(graph).TOOL_NAMES)
    assert all(type(tool).__name__.startswith("Fake") == (tool.name not in code) for tool in tools)


@pytest.mark.parametrize(("graph", "case"), CASES)
def test_ticket_search_finds_something_only_when_the_case_says_so(
    graph: str,
    case:  SearchCase,
) -> None:
    """Sprawdza, czy wyszukiwanie zgłoszeń w narzędziach sprawy coś znajduje wtedy i tylko wtedy,
    gdy sprawa ma `finds_tickets_and_docs`.

    Wyłapuje sprawę „komunikat tylko w kodzie”, w której atrapy zgłoszeń jednak oddają materiał:
    model mógłby wskazać przyczynę z historycznej sprawy, a para nie mierzyłaby kodu."""
    tool  = next(tool for tool in case_tools(case) if tool.name == "find_tickets_vector")
    query = FindTicketsVectorQuery(problem="Brak nowych przesyłek.", symptoms="Nic nie przychodzi.")
    found = asyncio.run(tool.find(query))

    assert bool(found.tickets) == case.finds_tickets_and_docs


@pytest.mark.parametrize(("graph", "case"), MESSAGE_CASES)
def test_a_case_quoting_a_screen_message_finds_no_tickets_or_docs(
    graph: str,
    case:  SearchCase,
) -> None:
    """Sprawdza, czy sprawa, której zgłoszenie cytuje komunikat z ekranu, ma puste wyszukiwanie
    zgłoszeń i instrukcji.

    Wyłapuje sprawę „komunikat tylko w kodzie” albo „komunikatu nie ma nigdzie”, w której atrapy
    zgłoszeń i instrukcji niosą materiał: model mógłby wytłumaczyć komunikat historyczną sprawą,
    a para nie mierzyłaby tego, czy znajduje go w kodzie."""
    assert not case.finds_tickets_and_docs
