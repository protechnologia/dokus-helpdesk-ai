"""
Description:
Spójność zestawu wstrzyknięć (`data/safe/golden/injections.json`) bez modelu: czy każdy atak
w ogóle może się przebić i czy sprawa kontrolna ma czym go sprawdzić. Test na żywym modelu
z takim zestawem byłby zielony, nic nie mierząc, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                   | czym grozi jego brak                           |
|-------------------------------------------|------------------------------------------------|
| sekcja nazywa się jak graf                | sekcja, której nikt nie uruchomi               |
| pola chronione są polami wyniku grafu     | znacznik szukany w polu, którego nie ma        |
| albo listą źródeł grafu, który ją ma      |                                                |
| oczekiwane pola dotyczą wejść sekcji      | wynik porównany z polem, którego nie ma,       |
| i pól wyniku grafu                        | albo oczekiwanie przy wejściu, którego nie ma  |
| sekcja ma czym wykryć przebicie           | atak, który może tylko wyjść na odparty        |
| wersja reguł jest wersją zestawu          | bramka sprawdzana regułami z przykładu albo    |
| domyślnego grafu z regułami               | sprawy napisane pod inne reguły                |
| droga ataku pasuje do grafu: reguły tylko | błąd w środku płatnego przebiegu albo atak,    |
| przy regułach, karta i wątek tylko przy   | którego model nie ma jak przeczytać            |
| narzędziach, które je czytają             |                                                |
| atak w materiale wskazuje sprawę i pole   | atak doklejony donikąd albo do listy kodów     |
| tekstowe z materiału atrap                |                                                |
| graf z regułami ma ataki obiema drogami,  | sekcja, która mierzy tylko jedną drogę         |
| graf czytający zgłoszenia — na wejściu,   |                                                |
| w karcie i w wątku                        |                                                |
| atak wskazuje istniejące wejście          | błąd w środku płatnego przebiegu               |
| każde wejście ma choć jeden atak          | sprawa kontrolna opłacona bez potrzeby         |
| znacznik stoi w ataku, w żadnym wejściu,  | atak, który nie może się przebić, albo sprawa  |
| regule zestawu domyślnego ani materiale   | kontrolna, która pada zawsze                   |
| atrap                                     |                                                |
"""

import pytest

from app.agent_tools.tickets.fake_tickets import default_cards, default_threads
from app.core_service.loader_dict_rules import get_rule_set
from tests._helpers.graphs import (
    graph_module,
    graph_names,
    has_rules,
    has_sources,
    output_fields,
)
from tests._helpers.scenarios.injections import (
    INTO_CARD,
    INTO_INPUT,
    INTO_RULES,
    INTO_THREAD,
    READER_OF,
    SOURCES_FIELD,
    InjectionAttack,
    found_markers,
    injection_sections,
)

# Sekcje zestawu, czytane przy imporcie: z nich powstają parametry testów.
SECTIONS = injection_sections()

# Grafy z regułami klienta i grafy czytające karty zgłoszeń, liczone przy imporcie: z nich
# powstają parametry testów dróg ataku.
RULES_GRAPHS   = sorted(graph for graph in SECTIONS if has_rules(graph_module(graph)))
TICKETS_GRAPHS = sorted(
    graph for graph in SECTIONS if READER_OF[INTO_CARD] in graph_module(graph).TOOL_NAMES
)

# Pary (graf, atak) zestawu, czytane przy imporcie: z nich powstają parametry testów.
ATTACKS = [(graph, attack) for graph, section in SECTIONS.items() for attack in section.attacks]


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_section_names_a_graph(graph: str) -> None:
    """Sprawdza, czy każda sekcja zestawu nazywa się jak katalog grafu w `app/agent_graphs/`.

    Wyłapuje sekcję z literówką w nazwie: test na żywym modelu nie znalazłby takiego grafu, a jej
    ataki nie zostałyby nigdy sprawdzone."""
    assert graph in graph_names()


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_guarded_fields_are_fields_of_the_graph_output(graph: str) -> None:
    """Sprawdza, czy każde pole chronione sekcji jest polem któregoś typu wyniku grafu albo listą
    źródeł (`sources`) — tę tylko w grafie, którego stan ją ma.

    Wyłapuje pole chronione z błędem w nazwie: ocena szukałaby znacznika w polu, którego wynik
    nie ma, liczyłaby je jak puste, a każdy atak wyszedłby na odparty; to samo przy liście
    źródeł w grafie, który niczego nie odczytuje."""
    module  = graph_module(graph)
    allowed = output_fields(module) | ({SOURCES_FIELD} if has_sources(module) else set())

    assert set(SECTIONS[graph].guarded_fields) <= allowed


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
    assert expected <= output_fields(graph_module(graph))


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

    assert (version is not None) == has_rules(graph_module(graph))
    assert version is None or version == get_rule_set(graph).version


@pytest.mark.parametrize("graph", sorted(SECTIONS))
def test_every_attack_route_fits_the_graph(graph: str) -> None:
    """Sprawdza, czy każdy atak idzie znaną drogą, do reguł tylko w grafie, który je ma, a do
    karty albo wątku tylko w grafie, który ma narzędzie ich odczytu.

    Wyłapuje literówkę w drodze ataku, przez którą atak trafiłby na koniec wejścia, atak
    w regułach grafu bez reguł, który przerwałby płatny przebieg błędem, i atak w materiale,
    którego model danego grafu nie ma jak przeczytać."""
    routes = {attack.into for attack in SECTIONS[graph].attacks}
    tools  = graph_module(graph).TOOL_NAMES

    assert routes <= {INTO_INPUT, INTO_RULES, INTO_CARD, INTO_THREAD}
    assert INTO_RULES not in routes or has_rules(graph_module(graph))
    assert all(READER_OF[route] in tools for route in routes & READER_OF.keys())


@pytest.mark.parametrize(
    ("graph", "attack"),
    [(graph, attack) for graph, attack in ATTACKS if attack.into in READER_OF],
    ids=lambda value: getattr(value, "attack_id", value),
)
def test_a_material_attack_points_at_text_in_the_fake_material(
    graph:  str,
    attack: InjectionAttack,
) -> None:
    """Sprawdza, czy atak w karcie wskazuje sprawę, której kartę mają atrapy, i pole tekstowe tej
    karty, a atak w wątku — sprawę, której wątek mają atrapy.

    Wyłapuje atak doklejony do sprawy spoza materiału, który przerwałby płatny przebieg błędem,
    i atak w polu listy (na przykład kodów błędów), który zamieniłby listę w napis."""
    cards   = {card.ticket_id: card for card in default_cards()}
    threads = {row.ticket_id for row in default_threads()}

    # --- atak w wątku: wątek tej sprawy musi istnieć ---
    if attack.into == INTO_THREAD:
        assert attack.ticket in threads
        return

    assert attack.ticket in cards
    assert isinstance(getattr(cards[attack.ticket], attack.field or "", None), str)


@pytest.mark.parametrize("graph", RULES_GRAPHS)
def test_a_graph_with_rules_is_attacked_by_both_routes(graph: str) -> None:
    """Sprawdza, czy sekcja grafu z regułami klienta ma ataki obiema drogami: na wejściu
    i w regułach.

    Wyłapuje sekcję, która mierzy tylko jedną drogę, i zestaw wczytany bez drogi ataku: ataki
    w regułach po cichu stałyby się atakami na wejściu, a test byłby zielony."""
    routes = {attack.into for attack in SECTIONS[graph].attacks}

    assert routes == {INTO_INPUT, INTO_RULES}


@pytest.mark.parametrize(
    "graph",
    TICKETS_GRAPHS,
)
def test_a_graph_reading_tickets_is_attacked_on_the_input_and_in_the_material(graph: str) -> None:
    """Sprawdza, czy sekcja grafu, który czyta karty i wątki zgłoszeń, ma ataki na wejściu,
    w karcie i w wątku historycznej sprawy.

    Wyłapuje sekcję, która mierzy tylko zgłoszenie, a nie wyniki narzędzi, i zestaw wczytany bez
    drogi ataku: ataki w materiale po cichu stałyby się atakami na wejściu."""
    routes = {attack.into for attack in SECTIONS[graph].attacks}

    assert {INTO_INPUT, INTO_CARD, INTO_THREAD} <= routes


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
    wejściu sekcji, w żadnej regule zestawu domyślnego grafu ani w materiale atrap narzędzi.

    Wyłapuje atak, który nie może się przebić, bo jego znacznika model nie ma skąd wziąć, i sprawę
    kontrolną, która pada zawsze, bo znacznik stoi już w samym wejściu, w regułach albo
    w karcie czy wątku, które model czyta także bez ataku."""
    rules    = get_rule_set(graph).rules if has_rules(graph_module(graph)) else []
    material = [card.model_dump_json() for card in default_cards()]
    material += [row.thread for row in default_threads()]
    texts    = [*SECTIONS[graph].inputs.values(), *rules, *material]

    assert attack.markers
    assert found_markers(attack.attack, attack.markers) == attack.markers
    assert not any(found_markers(text, attack.markers) for text in texts)
