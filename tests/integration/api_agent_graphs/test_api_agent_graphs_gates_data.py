"""
Description:
Spójność zestawu scenariuszy bramek (`data/safe/golden/gates.json`) bez modelu: czy sprawy
dotyczą reguł, które bramka naprawdę dostaje, i czy każda reguła ma komplet spraw. Test na żywym
modelu z takim zestawem liczyłby fałszywe alarmy i przepuszczenia na regułach, których już nie
ma, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                     | czym grozi jego brak                          |
|---------------------------------------------|-----------------------------------------------|
| sekcja nazywa bramkę: graf z regułami       | sekcja, której nikt nie uruchomi, albo graf,  |
| i werdyktem w wyniku                        | którego wynik nie ma werdyktu                 |
| wersja reguł jest wersją zestawu domyślnego | sprawy napisane pod inne reguły               |
| sprawa ma znany rodzaj i istniejącą regułę  | błąd w środku płatnego przebiegu albo sprawa  |
|                                             | przypisana regule, której nie ma              |
| każda reguła ma sprawę łamiącą, poprawną    | reguła mierzona tylko w jedną stronę          |
| i pułapkę                                   |                                               |
"""


import pytest

from app.core_model.graphs.verdict import Verdict
from app.core_service.loader_dict_rules import get_rule_set
from tests._helpers.graphs import graph_module, graph_names, has_rules, output_types
from tests._helpers.scenarios.gates import EXPECTED_VERDICTS, gate_sections

SECTIONS = gate_sections()


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_gate(graph: str) -> None:
    """Sprawdza, czy każda sekcja zestawu nazywa się jak katalog grafu, którego stan ma reguły
    klienta, a wynik jest werdyktem.

    Wyłapuje sekcję z literówką w nazwie, której sprawy nie zostałyby nigdy sprawdzone, i sekcję
    grafu, który nie jest bramką: ocena czytałaby werdykt z wyniku, który go nie ma."""
    assert graph in graph_names()

    module = graph_module(graph)

    assert has_rules(module)
    assert Verdict in output_types(module)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_rules_version_is_the_version_of_the_default_rule_set(graph: str) -> None:
    """Sprawdza, czy sekcja podaje wersję zestawu domyślnego reguł bramki, z którego test bierze
    reguły.

    Wyłapuje zestaw reguł zmieniony bez przejrzenia spraw: łamiąca sprawa mogłaby już nie łamać
    żadnej reguły, a test na żywym modelu odmówiłby dopiero po wyborze płatnych testów."""
    assert SECTIONS[graph].rules_version == get_rule_set(graph).version


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_cases_have_unique_ids_known_kinds_and_existing_rules(graph: str) -> None:
    """Sprawdza, czy identyfikatory spraw w sekcji się nie powtarzają, każda sprawa ma znany
    rodzaj i wskazuje regułę, która stoi w zestawie domyślnym (numer od 1).

    Wyłapuje rodzaj z literówką, na którym test przerwałby się w środku płatnego przebiegu,
    i sprawę przypisaną regule spoza zestawu, której liczniki w raporcie nic nie znaczą."""
    cases = SECTIONS[graph].cases
    ids   = [case.case_id for case in cases]
    rules = len(get_rule_set(graph).rules)

    assert len(ids) == len(set(ids))
    assert all(case.kind in EXPECTED_VERDICTS for case in cases)
    assert all(1 <= case.rule <= rules for case in cases)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_rule_has_a_breaking_a_correct_and_a_trap_case(graph: str) -> None:
    """Sprawdza, czy każda reguła zestawu domyślnego ma w sekcji sprawę łamiącą, poprawną
    i pułapkę.

    Wyłapuje regułę mierzoną w jedną stronę: bez sprawy łamiącej nie widać przepuszczeń, a bez
    poprawnej i pułapki — fałszywych alarmów, które bolą bardziej."""
    cases = SECTIONS[graph].cases
    rules = set(range(1, len(get_rule_set(graph).rules) + 1))

    for kind in EXPECTED_VERDICTS:
        assert {case.rule for case in cases if case.kind == kind} == rules, kind
