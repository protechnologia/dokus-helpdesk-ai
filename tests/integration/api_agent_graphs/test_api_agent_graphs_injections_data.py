"""
Description:
Spójność zestawu wstrzyknięć (`data/safe/golden/injections.json`) bez modelu: czy każdy atak
w ogóle może się przebić i czy sprawa kontrolna ma czym go sprawdzić. Test na żywym modelu
z takim zestawem byłby zielony, nic nie mierząc, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                   | czym grozi jego brak                           |
|-------------------------------------------|------------------------------------------------|
| sekcja nazywa się jak graf                | sekcja, której nikt nie uruchomi               |
| pola chronione są polami wyniku grafu     | znacznik szukany w polu, którego nie ma        |
| atak wskazuje istniejące wejście          | błąd w środku płatnego przebiegu               |
| każde wejście ma choć jeden atak          | sprawa kontrolna opłacona bez potrzeby         |
| znacznik stoi w ataku, w żadnym wejściu   | atak, który nie może się przebić, albo sprawa  |
|                                           | kontrolna, która pada zawsze                   |
"""

import importlib
import pkgutil
from typing import get_args

import pytest
from pydantic import BaseModel

import app.agent_graphs
from tests.helpers_injections import InjectionAttack, found_markers, injection_sections

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
    fields = {name for output_type in _output_types(graph) for name in output_type.model_fields}

    assert set(SECTIONS[graph].guarded_fields) <= fields


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
    wejściu sekcji.

    Wyłapuje atak, który nie może się przebić, bo jego znacznika model nie ma skąd wziąć, i sprawę
    kontrolną, która pada zawsze, bo znacznik stoi już w samym wejściu."""
    inputs = SECTIONS[graph].inputs.values()

    assert attack.markers
    assert found_markers(attack.attack, attack.markers) == attack.markers
    assert not any(found_markers(text, attack.markers) for text in inputs)
