import importlib
import pkgutil

import pytest

import app.agent_nodes
from app.agent_nodes import Node


def all_nodes() -> list[type[Node]]:
    """
    Description:
    Zbiera wszystkie klasy węzłów z pakietów w `app/agent_nodes/` — także tych, których jeszcze nie
    ma. Nowy węzeł to nowy katalog, więc test ma go znaleźć sam.

    Example args:
        (brak)

    Example result:
        [AnonymizeNode, FakeAgentNode, FakeRunToolsNode, FakeRespondNode]
    """
    for module in pkgutil.iter_modules(app.agent_nodes.__path__):
        if module.ispkg:
            importlib.import_module(f"app.agent_nodes.{module.name}")

    found:   list[type[Node]] = []
    pending: list[type[Node]] = list(Node.__subclasses__())

    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())

    return found


NODES = all_nodes()


def package_of(
    node: type[Node],  # np. FakeAgentNode
) -> str:
    """
    Description:
    Nazwa pakietu węzła w `app/agent_nodes/`.

    Example args:
        node=FakeAgentNode

    Example result:
        "agent"
    """
    return node.__module__.split(".")[2]


def test_every_node_package_brings_a_node() -> None:
    """Sprawdza, czy każdy katalog w `app/agent_nodes/` wnosi co najmniej jeden węzeł, widoczny po
    zaimportowaniu tego katalogu.

    Wyłapuje katalog węzła, którego `__init__.py` nie importuje swoich klas: taki węzeł wypadłby
    z pozostałych testów kontraktu i nikt by tego nie zauważył."""
    modules  = pkgutil.iter_modules(app.agent_nodes.__path__)
    packages = {module.name for module in modules if module.ispkg}

    assert packages <= {package_of(node) for node in NODES}


@pytest.mark.parametrize("node", NODES, ids=lambda cls: cls.__name__)
def test_every_node_is_named_after_its_package(node: type[Node]) -> None:
    """Sprawdza, czy każdy węzeł, właściwy i atrapa, nosi nazwę swojego katalogu: węzły z `agent/`
    nazywają się „agent", z `run_tools/` „run_tools" i tak dalej.

    Wyłapuje węzeł o innej nazwie niż katalog: atrapa i węzeł właściwy mają wpinać się do grafu pod
    tą samą nazwą, a po tej nazwie rozpoznają je też testy grafów."""
    assert node.name == package_of(node)


def test_anonymize_has_no_fake_node() -> None:
    """Sprawdza, czy w katalogu `anonymize/` jest wyłącznie węzeł właściwy, bez atrapy.

    Wyłapuje dodanie atrapy węzła anonimizacji: byłaby drugą drogą obok anonimizacji, której
    w testach grafów nie da się odróżnić od prawdziwej."""
    anonymize_nodes = [node for node in NODES if package_of(node) == "anonymize"]

    assert [node.__module__ for node in anonymize_nodes] == ["app.agent_nodes.anonymize.node"]
