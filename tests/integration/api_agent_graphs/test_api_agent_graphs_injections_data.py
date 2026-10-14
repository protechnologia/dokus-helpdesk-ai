"""
Description:
Spójność zestawu wstrzyknięć (`data/safe/golden/injections.json`) bez modelu: czy każdy atak
w ogóle może się przebić i czy sprawa kontrolna ma czym go sprawdzić. Test na żywym modelu
z takim zestawem byłby zielony, nic nie mierząc, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                   | czym grozi jego brak                           |
|-------------------------------------------|------------------------------------------------|
| sekcja nazywa się jak graf                | sekcja, której nikt nie uruchomi               |
| pola chronione są polami wyniku grafu     | znacznik szukany w polu, którego nie ma        |
| oczekiwane pola dotyczą wejść sekcji      | wynik porównany z polem, którego nie ma,       |
| i pól wyniku grafu                        | albo oczekiwanie przy wejściu, którego nie ma  |
| sekcja ma czym wykryć przebicie           | atak, który może tylko wyjść na odparty        |
| wersja reguł jest wersją zestawu          | bramka sprawdzana regułami z przykładu albo    |
| domyślnego grafu z regułami               | sprawy napisane pod inne reguły                |
| atak w regułach tylko w grafie z regułami | błąd w środku płatnego przebiegu               |
| atak wskazuje istniejące wejście          | błąd w środku płatnego przebiegu               |
| każde wejście ma choć jeden atak          | sprawa kontrolna opłacona bez potrzeby         |
| znacznik stoi w ataku, w żadnym wejściu   | atak, który nie może się przebić, albo sprawa  |
| ani w żadnej regule zestawu domyślnego    | kontrolna, która pada zawsze                   |
"""

import importlib
import pkgutil
from typing import get_args

import pytest
from pydantic import BaseModel

import app.agent_graphs
from app.core_service.loader_dict_rules import get_rule_set
from tests.helpers_injections import (
    INTO_INPUT,
    INTO_RULES,
    InjectionAttack,
    found_markers,
    injection_sections,
)

SECTIONS = injection_sections()

GRAPH_NAMES = {
    module.name
    for module in pkgutil.iter_modules(app.agent_graphs.__path__)
    if module.ispkg
}

# Pary (graf, atak) zestawu, czytane przy imporcie: z nich powstają parametry testów.
ATTACKS = [(graph, attack) for graph, section in SECTIONS.items() for attack in section.attacks]


def _output_types(
    graph: str,  # np. "suggest_handoff"
) -> list[type[BaseModel]]:
    """
    Description:
    Typy wyniku grafu, odczytane z pola `output` jego stanu; bez `None`.

    Example args:
        graph="suggest_handoff"

    Example result:
        [Proposal]
    """
    module     = importlib.import_module(f"app.agent_graphs.{graph}")
    annotation = module.STATE.model_fields["output"].annotation
    types      = [arg for arg in get_args(annotation) if arg is not type(None)]

    return types


def _output_fields(
    graph: str,  # np. "suggest_handoff"
) -> set[str]:
    """
    Description:
    Nazwy pól wszystkich typów wyniku grafu.

    Example args:
        graph="suggest_handoff"

    Example result:
        {"text", "internal_notes"}
    """
    return {name for output_type in _output_types(graph) for name in output_type.model_fields}


def _has_rules(
    graph: str,  # np. "gate_reply"
) -> bool:
    """
    Description:
    Czy stan grafu ma reguły klienta.

    Example args:
        graph="gate_reply"

    Example result:
        True
    """
    module = importlib.import_module(f"app.agent_graphs.{graph}")

    return "rules" in module.STATE.model_fields


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph(graph: str) -> None:
    """Sprawdza, czy każda sekcja zestawu nazywa się jak katalog grafu w `app/agent_graphs/`.

    Wyłapuje sekcję z literówką w nazwie: test na żywym modelu nie znalazłby takiego grafu, a jej
    ataki nie zostałyby nigdy sprawdzone."""
    assert graph in GRAPH_NAMES


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_guarded_fields_are_fields_of_the_graph_output(graph: str) -> None:
    """Sprawdza, czy każde pole chronione sekcji jest polem któregoś typu wyniku grafu.

    Wyłapuje pole chronione z błędem w nazwie: ocena szukałaby znacznika w polu, którego wynik
    nie ma, liczyłaby je jak puste, a każdy atak wyszedłby na odparty."""
    assert set(SECTIONS[graph].guarded_fields) <= _output_fields(graph)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_expected_fields_belong_to_inputs_and_to_the_graph_output(graph: str) -> None:
    """Sprawdza, czy oczekiwane pola wyniku stoją przy wejściach z tej sekcji i czy każde jest
    polem któregoś typu wyniku grafu.

    Wyłapuje oczekiwanie przy wejściu z literówką, które nikogo nie dotyczy, i pole z błędem
    w nazwie: wynik nie ma takiego pola, więc każda sprawa, także kontrolna, wyszłaby na
    przebitą."""
    section  = SECTIONS[graph]
    expected = {name for fields in section.expected.values() for name in fields}

    assert set(section.expected) <= set(section.inputs)
    assert expected <= _output_fields(graph)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_can_detect_a_breach(graph: str) -> None:
    """Sprawdza, czy sekcja ma czym wykryć przebicie: pola chronione albo oczekiwane pola wyniku
    przy każdym wejściu.

    Wyłapuje sekcję bramki, w której zabrakło oczekiwanego werdyktu przy wejściu: bez pól
    chronionych atak na takie wejście wyszedłby na odparty, cokolwiek bramka by orzekła."""
    section = SECTIONS[graph]

    assert section.guarded_fields or set(section.expected) == set(section.inputs)


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_rules_version_is_the_version_of_the_default_rule_set(graph: str) -> None:
    """Sprawdza, czy sekcja grafu z regułami klienta podaje wersję reguł i czy to wersja zestawu
    domyślnego grafu, a sekcja grafu bez reguł wersji nie podaje.

    Wyłapuje sekcję bramki bez wersji, w której test na żywym modelu sprawdzałby bramkę regułami
    z jej stanu przykładowego zamiast tych, które bierze trasa, i sekcję napisaną pod reguły,
    których już nie ma: test na żywym modelu odmówiłby dopiero po wyborze płatnych testów."""
    version = SECTIONS[graph].rules_version

    assert (version is not None) == _has_rules(graph)
    assert version is None or version == get_rule_set(graph).version


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_attacks_go_into_rules_only_in_a_graph_with_rules(graph: str) -> None:
    """Sprawdza, czy każdy atak idzie na wejście albo do reguł klienta, a do reguł tylko w grafie,
    który je ma.

    Wyłapuje literówkę w drodze ataku, przez którą atak w regułach trafiłby na koniec wejścia,
    i atak w regułach grafu bez reguł, który przerwałby płatny przebieg błędem."""
    section = SECTIONS[graph]
    routes  = {attack.into for attack in section.attacks}

    assert routes <= {INTO_INPUT, INTO_RULES}
    assert INTO_RULES not in routes or _has_rules(graph)


@pytest.mark.parametrize("graph", sorted(graph for graph in SECTIONS if _has_rules(graph)))
def test_a_graph_with_rules_is_attacked_by_both_routes(graph: str) -> None:
    """Sprawdza, czy sekcja grafu z regułami klienta ma ataki obiema drogami: na wejściu
    i w regułach.

    Wyłapuje sekcję, która mierzy tylko jedną drogę, i zestaw wczytany bez drogi ataku: ataki
    w regułach po cichu stałyby się atakami na wejściu, a test byłby zielony."""
    routes = {attack.into for attack in SECTIONS[graph].attacks}

    assert routes == {INTO_INPUT, INTO_RULES}


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_attack_ids_are_unique_and_every_input_is_attacked(graph: str) -> None:
    """Sprawdza, czy identyfikatory ataków w sekcji się nie powtarzają, każdy atak wskazuje
    wejście z tej sekcji i do każdego wejścia doklejany jest choć jeden atak.

    Wyłapuje atak na wejście, którego nie ma — wyszłoby to dopiero w środku płatnego przebiegu —
    i wejście bez ataków, którego sprawa kontrolna nic nie sprawdza, a kosztuje."""
    section  = SECTIONS[graph]
    ids      = [attack.attack_id for attack in section.attacks]
    attacked = {attack.input_id for attack in section.attacks}

    assert len(ids) == len(set(ids))
    assert attacked == set(section.inputs)


@pytest.mark.parametrize(
    ("graph", "attack"),
    ATTACKS,
    ids=lambda value: getattr(value, "attack_id", value),
)
def test_every_marker_stands_in_its_attack_and_in_no_input(
    graph:  str,
    attack: InjectionAttack,
) -> None:
    """Sprawdza, czy atak ma znaczniki, każdy stoi w tekście ataku i żaden nie stoi w żadnym
    wejściu sekcji ani w żadnej regule zestawu domyślnego grafu.

    Wyłapuje atak, który nie może się przebić, bo jego znacznika model nie ma skąd wziąć, i sprawę
    kontrolną, która pada zawsze, bo znacznik stoi już w samym wejściu albo w regułach."""
    rules = get_rule_set(graph).rules if _has_rules(graph) else []
    texts = [*SECTIONS[graph].inputs.values(), *rules]

    assert attack.markers
    assert found_markers(attack.attack, attack.markers) == attack.markers
    assert not any(found_markers(text, attack.markers) for text in texts)
