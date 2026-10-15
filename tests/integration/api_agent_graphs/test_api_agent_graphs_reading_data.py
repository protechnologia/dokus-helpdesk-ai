"""
Description:
Spójność zestawu scenariuszy czytania (`data/safe/golden/reading.json`) bez modelu: czy sprawy idą
na grafach z narzędziami wiedzy, czy klucze źródeł wskazują materiał, który atrapy znajdują
i graf umie przeczytać, czy fakty do nazwania stoją w tym materiale, a nie w zgłoszeniu, i czy
licznik narzędzi kodu zna wszystkie narzędzia kodu grafów. Test na żywym modelu z takim zestawem
mierzyłby co innego, niż obiecuje, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                        | czym grozi jego brak                          |
|------------------------------------------------|-----------------------------------------------|
| graf z pola `graphs` ma listę źródeł           | sprawa, której nikt nie uruchomi, albo graf,  |
|                                                | który niczego nie odczytuje                   |
| każdy graf ma sprawę z `must_read`             | graf, na którym test nie ma czego sprawdzać   |
| sprawy mają różne identyfikatory i co najmniej | sprawa, która nie idzie na żadnym grafie,     |
| jeden graf, bez powtórzeń                      | albo dwie sprawy o jednym identyfikatorze     |
| zgłoszenie ma kształt wątku                    | sprawa, która nie wygląda jak wejście tras    |
| klucz źródła wskazuje materiał, który atrapy   | warunek nie do spełnienia: model nie ma czego |
| znajdują, a graf sprawy umie przeczytać        | przeczytać albo nie ma czym                   |
| klucz nie jest naraz oczekiwany i niepożądany  | licznik sprzeczny sam ze sobą                 |
| wymagane karty niosą różne przyczyny           | sprawa, która nie mierzy czytania przy jednym |
|                                                | objawie i kilku przyczynach                   |
| fakt do nazwania stoi w materiale, nie stoi    | licznik zawsze pusty albo spełniany           |
| w zgłoszeniu                                   | przepisaniem zgłoszenia                       |
| wariant faktu do wykluczenia stoi w jednej     | licznik, który liczy linię o innej sprawie    |
| sprawie albo sekcji materiału                  | jako wykluczenie tej przyczyny                |
| sprawa z przyczyną wykluczoną ma wątek i parę  | brak porównania: nie wiadomo, czy uwagi       |
| bez wątku, o tym samym temacie                 | wykluczają przez wątek, czy zawsze            |
| licznik zna każde narzędzie kodu grafów        | wywołania nowego narzędzia kodu, których      |
|                                                | raport nie policzy                            |
"""

import pytest

from app.agent_tools.tickets.fake_tickets import default_cards
from tests._helpers.graphs import graph_module, graph_names, has_sources
from tests._helpers.scenarios.reading import (
    CODE_TOOLS,
    READERS,
    ReadingCase,
    case_keys,
    found_material,
    material_text,
    material_units,
    reading_cases,
    reading_sections,
)
from tests._helpers.scenarios.solution import mentions, ticket_subject

# Sekcje zestawu (graf → sprawy z pola `graphs`), czytane przy imporcie: z nich powstają
# parametry testów na graf.
SECTIONS = reading_sections()

# Sprawy zestawu, każda raz, czytane przy imporcie: z nich powstają parametry testów samej
# sprawy, nazwane jej identyfikatorem. Obok podzbiory spraw, których dotyczy tylko część testów.
CASES         = [pytest.param(case, id=case.case_id) for case in reading_cases()]
CARD_CASES    = [
    param for param in CASES
    if any(key.startswith("tickets:") for key in param.values[0].must_read)
]
NAME_CASES    = [param for param in CASES if param.values[0].should_name]
EXCLUDE_CASES = [param for param in CASES if param.values[0].should_exclude]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_graph_of_the_set_reads_material(graph: str) -> None:
    """Sprawdza, czy każdy graf, który sprawy wymieniają w `graphs`, nazywa się jak katalog grafu
    i ma w stanie listę źródeł.

    Wyłapuje graf z literówką w nazwie, na którym sprawy nie zostałyby nigdy sprawdzone, i graf
    bez narzędzi wiedzy: warunek przeczytanego materiału nie miałby czego sprawdzać."""
    assert graph in graph_names()
    assert has_sources(graph_module(graph))


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_graph_has_a_case_that_must_read(graph: str) -> None:
    """Sprawdza, czy każdy graf ma co najmniej jedną sprawę z wymaganymi źródłami.

    Wyłapuje graf, na którym idą same liczniki: test przeczytanego materiału przechodziłby na nim
    zawsze, niczego nie sprawdzając."""
    assert any(case.must_read for case in SECTIONS[graph].cases)


def test_every_case_has_its_own_id_and_runs_on_listed_graphs() -> None:
    """Sprawdza, czy identyfikatory spraw w zestawie się nie powtarzają, a każda sprawa wymienia
    w `graphs` co najmniej jeden graf, każdy raz.

    Wyłapuje sprawę z pustą listą grafów, której nikt nie uruchomi, graf wymieniony dwa razy,
    przez co sprawa szłaby na nim podwójnie, i dwie sprawy o jednym identyfikatorze w raporcie."""
    cases = reading_cases()
    ids   = [case.case_id for case in cases]

    assert len(ids) == len(set(ids))
    assert all(case.graphs for case in cases)
    assert all(len(case.graphs) == len(set(case.graphs)) for case in cases)


@pytest.mark.parametrize("case", CASES)
def test_every_case_is_a_ticket_with_a_thread(case: ReadingCase) -> None:
    """Sprawdza, czy każda sprawa ma kształt wątku z `RawTicket.as_thread()`: nagłówek zgłoszenia,
    temat i opis zgłaszającego.

    Wyłapuje sprawę, która nie wygląda jak wejście tras grafów: model dostałby inny kształt
    niż na produkcji, a wynik nie mówiłby nic o prawdziwej sprawie."""
    assert case.text.startswith("ZGŁOSZENIE ")
    assert "\nTemat: " in case.text
    assert "\nOPIS ZGŁASZAJĄCEGO:\n" in case.text


@pytest.mark.parametrize("case", CASES)
def test_every_source_key_is_found_and_readable_on_the_case_graphs(case: ReadingCase) -> None:
    """Sprawdza, czy każdy klucz źródła ze sprawy wskazuje materiał, który atrapy wyszukiwań
    znajdują i umieją odczytać, a każdy graf sprawy ma narzędzie odczytu tego materiału.

    Wyłapuje literówkę w kluczu i klucz materiału, którego atrapa nie znajduje albo graf nie
    czyta: warunek przeczytanego materiału byłby nie do spełnienia, a licznik zawsze pusty."""
    found = found_material()

    for key in case_keys(case):
        material = key.split(":", 1)[0]

        assert key in found, key

        for graph in case.graphs:
            assert set(READERS[material]) & set(graph_module(graph).TOOL_NAMES), (graph, key)


@pytest.mark.parametrize("case", CASES)
def test_a_key_is_never_both_wanted_and_unwanted(case: ReadingCase) -> None:
    """Sprawdza, czy żaden klucz źródła nie jest w sprawie naraz wymagany albo oczekiwany
    i niepożądany.

    Wyłapuje licznik sprzeczny sam ze sobą: to samo przeczytane źródło liczyłoby się w raporcie
    jako dobre i złe."""
    wanted = {*case.must_read, *case.should_read}

    assert not wanted & set(case.should_not_read)


@pytest.mark.parametrize("case", CARD_CASES)
def test_required_cards_carry_different_causes(case: ReadingCase) -> None:
    """Sprawdza, czy karty, które sprawa każe przeczytać, są co najmniej dwie i każda niesie inną
    przyczynę.

    Wyłapuje sprawę, która nie mierzy tego, po co scenariusz powstał: przy kartach o jednej
    przyczynie model, który czyta jedną kartę, nie traci żadnej informacji."""
    numbers = {key.split(":", 1)[1] for key in case.must_read if key.startswith("tickets:")}
    causes  = [card.cause for card in default_cards() if card.ticket_id in numbers]

    assert len(causes) == len(numbers) >= 2
    assert len(set(causes)) == len(causes)


@pytest.mark.parametrize("case", NAME_CASES)
def test_a_fact_to_name_stands_in_the_material_and_not_in_the_ticket(case: ReadingCase) -> None:
    """Sprawdza, czy każdy fakt, który wynik ma nazwać, stoi w materiale atrap (kartach albo
    sekcjach), a nie stoi w zgłoszeniu; fakt do wykluczenia ma stać w materiale.

    Wyłapuje licznik zawsze pusty — faktu nie ma w materiale, więc model nie ma go skąd wziąć —
    i licznik spełniany przepisaniem zgłoszenia, który niczego o czytaniu nie mówi."""
    material = material_text()

    assert all(mentions(material, fact) for fact in (*case.should_name, *case.should_exclude))
    assert not any(mentions(case.text, fact) for fact in case.should_name)


@pytest.mark.parametrize("case", EXCLUDE_CASES)
def test_every_variant_of_a_fact_to_exclude_stands_in_one_source_only(case: ReadingCase) -> None:
    """Sprawdza, czy każdy wariant faktu do wykluczenia stoi w materiale atrap dokładnie w jednej
    sprawie albo sekcji: w karcie i wątku jednego zgłoszenia albo w jednej sekcji dokumentacji.

    Wyłapuje wariant, który łapie cudzą przyczynę — „limit” stoi też przy limitach zasobów
    w wątku 90011 — więc linia uwag o innej sprawie liczyłaby się jako wykluczenie tej przyczyny,
    jak w pierwszych przebiegach na żywym modelu."""
    units = material_units()

    for fact in case.should_exclude:
        for variant in fact:
            holders = [key for key, text in units.items() if mentions(text, (variant,))]

            assert len(holders) == 1, (variant, holders)


@pytest.mark.parametrize("case", EXCLUDE_CASES)
def test_an_excluded_cause_comes_with_a_thread_and_a_pair(case: ReadingCase) -> None:
    """Sprawdza, czy sprawa z przyczyną do wykluczenia ma wątek z komentarzami, a zestaw ma jej
    parę: ten sam temat zgłoszenia, bez wątku i bez przyczyny do wykluczenia, na tych samych
    grafach.

    Wyłapuje sprawę bez wątku, w której klient niczego nie mógł wykluczyć, i sprawę bez pary:
    nie dałoby się powiedzieć, czy uwagi wykluczają przyczynę przez odpowiedź klienta, czy
    zawsze."""
    pairs = [
        other for other in reading_cases()
        if ticket_subject(other.text) == ticket_subject(case.text)
        and not other.should_exclude
        and "\nKOMENTARZ " not in other.text
        and set(case.graphs) <= set(other.graphs)
    ]

    assert "\nKOMENTARZ " in case.text
    assert pairs, case.case_id


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_code_tools_cover_every_code_tool_of_the_graph(graph: str) -> None:
    """Sprawdza, czy lista narzędzi kodu, której wywołania liczy raport, to dokładnie narzędzia
    kodu z `TOOL_NAMES` grafu.

    Wyłapuje nowe narzędzie kodu, którego wywołań raport by nie policzył — sprawa organizacyjna
    wyglądałaby na czystą, choć model sięgał po kod — i nazwę, której graf już nie zna."""
    code = {name for name in graph_module(graph).TOOL_NAMES if "code" in name}

    assert code == set(CODE_TOOLS)
