"""
Description:
Spójność zestawu scenariuszy „Popraw” (`data/safe/golden/polish.json`) bez modelu: czy każda
sprawa w ogóle może się nie udać i czy sprawdza tylko to, co da się porównać z notatkami. Test
na żywym modelu z takim zestawem byłby zielony, nic nie mierząc, albo czerwony z winy sprawy,
więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                       | czym grozi jego brak                        |
|-----------------------------------------------|---------------------------------------------|
| sekcja nazywa graf z zasadami klienta         | sekcja, której nikt nie uruchomi            |
| wersja zasad jest wersją zestawu domyślnego   | sprawy napisane pod inne zasady             |
| sprawy mają różne identyfikatory              | raport, w którym nie wiadomo, o którą chodzi |
| sekcja ma pułapki                             | test dopisanych nazw zielony przy wszystkim |
| każda sprawa ma słowo potoczne i fakt         | sprawa, która nie sprawdza redakcji albo    |
|                                               | zachowania treści                           |
| słowo potoczne i fakt stoją w notatkach       | słowo, które nie może zostać, albo fakt,    |
|                                               | który ginie zawsze                          |
| pułapka nie stoi w notatkach                  | dopisek, który jest wiernym przepisaniem    |
"""


import pytest

from app.core_service.loader_dict_rules import get_rule_set
from tests._helpers.graphs import graph_module, graph_names, has_rules, output_types
from tests._helpers.scenarios.polish import PolishCase, plain, polish_sections

SECTIONS = polish_sections()


# Pary (graf, sprawa) zestawu, czytane przy imporcie: z nich powstają parametry testów.
CASES = [(graph, case) for graph, section in SECTIONS.items() for case in section.cases]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph_with_rules(graph: str) -> None:
    """Sprawdza, czy każda sekcja zestawu nazywa się jak katalog grafu, którego stan ma zasady
    klienta, a wynik ma pole `text`.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i sekcję
    grafu, którego wynik nie ma tekstu do oceny."""
    assert graph in graph_names()

    module  = graph_module(graph)
    outputs = output_types(module)

    assert has_rules(module)
    assert outputs
    assert all("text" in output.model_fields for output in outputs)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_rules_version_is_the_version_of_the_default_rule_set(graph: str) -> None:
    """Sprawdza, czy sekcja podaje wersję zestawu domyślnego zasad stylu, z którego test bierze
    zasady, i czy identyfikatory spraw się nie powtarzają.

    Wyłapuje zasady zmienione bez przejrzenia spraw — test na żywym modelu odmówiłby dopiero po
    wyborze płatnych testów — i dwie sprawy o jednym identyfikatorze w raporcie."""
    ids = [case.case_id for case in SECTIONS[graph].cases]

    assert SECTIONS[graph].rules_version == get_rule_set(graph).version
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_a_section_sets_traps_for_added_names(graph: str) -> None:
    """Sprawdza, czy sekcja ma choć jedną sprawę z pułapkami.

    Wyłapuje zestaw albo jego wczytanie bez pułapek: test dopisanych nazw byłby wtedy zielony
    przy każdej odpowiedzi, bo sprawdzałby tylko liczby."""
    assert any(case.tempting for case in SECTIONS[graph].cases)


@pytest.mark.parametrize(
    ("graph", "case"),
    CASES,
    ids=lambda value: getattr(value, "case_id", value),
)
def test_every_word_and_fact_stands_in_the_notes_and_no_trap_does(
    graph: str,
    case:  PolishCase,
) -> None:
    """Sprawdza, czy sprawa ma słowo potoczne i fakt, czy każde jej słowo potoczne i każdy fakt
    stoją w notatkach, a żadna pułapka w nich nie stoi — w tym samym zapisie, w którym ocena
    szuka ich w tekście.

    Wyłapuje sprawę, która nie sprawdza redakcji albo zachowania treści, słowo potoczne
    z literówką, które nie może zostać w tekście, fakt, który ginie w każdej odpowiedzi,
    i pułapkę, która stoi w notatkach, więc jej przepisanie byłoby wiernością, a nie
    dopiskiem."""
    notes = plain(case.text)

    assert case.colloquial
    assert case.kept
    assert all(plain(word) in notes for word in case.colloquial)
    assert all(plain(fact) in notes for fact in case.kept)
    assert not any(plain(word) in notes for word in case.tempting)
