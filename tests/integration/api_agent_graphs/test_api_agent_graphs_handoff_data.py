"""
Description:
Spójność zestawu scenariuszy przekazania sprawy (`data/safe/golden/handoff.json`) bez modelu: czy
każda sprawa w ogóle może się nie udać i czy sprawdza tylko to, co da się porównać z wątkiem. Test
na żywym modelu z takim zestawem byłby zielony, nic nie mierząc, albo czerwony z winy sprawy, więc
te warunki pilnuje się w domyślnym `pytest`.

| warunek                                       | czym grozi jego brak                        |
|-----------------------------------------------|---------------------------------------------|
| sekcja nazywa graf bez reguł, z polem `text`  | sekcja, której nikt nie uruchomi            |
| sprawy mają różne identyfikatory              | raport, w którym nie wiadomo, o którą chodzi |
| wejście ma kształt `as_thread()`              | model dostaje coś innego niż z trasy        |
| sekcja ma pułapki i ostrzeżenie               | testy dopisków i ostrzeżeń zielone zawsze   |
| każdy fakt i pierwszy rdzeń stoją w wątku     | fakt, który ginie zawsze                    |
| pułapka nie stoi w wątku                      | dopisek, który jest wiernym przepisaniem    |
| fragmenty przykładu stoją w opisie narzędzia  | licznik pilnuje przykładu sprzed zmiany     |
| fragmenty przykładu nie stoją w żadnej sprawie | fałszywy alarm na wiernym podsumowaniu      |
"""


import pytest

from app.agent_graphs import suggest_handoff
from tests._helpers.graphs import graph_module, graph_names, has_rules, output_types
from tests._helpers.scenarios.handoff import (
    EXAMPLE_PHRASES,
    FAREWELL,
    GREETING,
    HandoffCase,
    handoff_sections,
)
from tests._helpers.scenarios.polish import plain

SECTIONS = handoff_sections()

# Pary (graf, sprawa) zestawu, czytane przy imporcie: z nich powstają parametry testów.
CASES = [(graph, case) for graph, section in SECTIONS.items() for case in section.cases]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph_without_rules(graph: str) -> None:
    """Sprawdza, czy każda sekcja zestawu nazywa się jak katalog grafu, którego stan nie ma reguł
    klienta, a wynik ma pole `text`.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i sekcję
    grafu, który bez reguł w ogóle nie ruszy."""
    assert graph in graph_names()

    module  = graph_module(graph)
    outputs = output_types(module)

    assert not has_rules(module)
    assert outputs
    assert all("text" in output.model_fields for output in outputs)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_section_can_fail_on_traps_and_warnings(graph: str) -> None:
    """Sprawdza, czy identyfikatory spraw się nie powtarzają, a sekcja ma sprawę z pułapkami
    i sprawę z ostrzeżeniem.

    Wyłapuje dwie sprawy o jednym identyfikatorze w raporcie i zestaw albo jego wczytanie bez list:
    testy dopisków i ostrzeżeń byłyby wtedy zielone przy każdej odpowiedzi."""
    cases = SECTIONS[graph].cases
    ids   = [case.case_id for case in cases]

    assert len(ids) == len(set(ids))
    assert any(case.tempting for case in cases)
    assert any(case.warning for case in cases)


@pytest.mark.parametrize(
    ("graph", "case"),
    CASES,
    ids=lambda value: getattr(value, "case_id", value),
)
def test_every_fact_stands_in_the_thread_and_no_trap_does(
    graph: str,
    case:  HandoffCase,
) -> None:
    """Sprawdza, czy sprawa ma kształt zgłoszenia z `as_thread()` i fakt, czy każdy jej fakt
    i pierwszy rdzeń ostrzeżenia stoją w wątku, a żadna pułapka w nim nie stoi — w tym samym
    zapisie, w którym ocena szuka ich w wiadomości.

    Wyłapuje sprawę, która nie sprawdza treści, fakt z literówką, który ginie w każdej odpowiedzi,
    ostrzeżenie, którego wątek nie niesie, i pułapkę, której przepisanie byłoby wiernością, a nie
    dopiskiem."""
    thread = plain(case.text)

    assert case.text.startswith("ZGŁOSZENIE ")
    assert case.kept
    assert all(plain(fact) in thread for fact in case.kept)
    assert not case.warning or plain(case.warning[0]) in thread
    assert not any(plain(word) in thread for word in case.tempting)


def test_the_example_phrases_and_layout_stand_in_the_tool_description() -> None:
    """Sprawdza, czy fragmenty przykładu, powitanie i pożegnanie, których szuka ocena, stoją
    w opisie narzędzia odpowiedzi.

    Wyłapuje przykład zmieniony w `respond_tool.md` bez zmiany stałych: licznik przepisania
    pilnowałby wtedy fragmentów, których model nigdy nie dostał, a ocena układu oczekiwałaby
    powitania, którego przykład już nie pokazuje."""
    description = plain(suggest_handoff.respond_tool().description)

    assert all(plain(phrase) in description for phrase in EXAMPLE_PHRASES)
    assert plain(GREETING) in description
    assert plain(FAREWELL) in description


@pytest.mark.parametrize(
    ("graph", "case"),
    CASES,
    ids=lambda value: getattr(value, "case_id", value),
)
def test_no_case_carries_the_example_phrases(graph: str, case: HandoffCase) -> None:
    """Sprawdza, czy żadne zgłoszenie zestawu nie niesie fragmentów przykładu z opisu pola `text`.

    Wyłapuje sprawę o podpisie albo certyfikacie: jej wierne podsumowanie wyszłoby jako treść
    przepisana z przykładu, czyli fałszywy alarm bez winy modelu."""
    thread = plain(case.text)

    assert not any(plain(phrase) in thread for phrase in EXAMPLE_PHRASES)
