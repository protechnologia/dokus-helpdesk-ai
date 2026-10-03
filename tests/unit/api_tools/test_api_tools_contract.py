import importlib
import pkgutil

import pytest
from pydantic import BaseModel

import app.tools
from app.tools import KnowledgeSource


def all_knowledge_sources() -> list[type[KnowledgeSource]]:
    """
    Description:
    Zbiera wszystkie klasy źródeł wiedzy z pakietów w `app/tools/` — także te, których jeszcze
    nie ma. Nowe narzędzie to nowy katalog, więc test ma je znaleźć sam, bez dopisywania do listy.

    Example args:
        (brak)

    Example result:
        [FakeFindTicketsVector, FakeFindDocsVector]
    """
    for module in pkgutil.iter_modules(app.tools.__path__):
        if module.ispkg:
            importlib.import_module(f"app.tools.{module.name}")

    found:   list[type[KnowledgeSource]] = []
    pending: list[type[KnowledgeSource]] = list(KnowledgeSource.__subclasses__())

    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())

    return found


SOURCES = all_knowledge_sources()


def test_every_tool_package_brings_a_source() -> None:
    """Pakiety narzędzi → co najmniej jedno źródło na pakiet: pusty katalog narzędzia oznacza,
    że importy w jego `__init__.py` coś pominęły."""
    packages = {module.name for module in pkgutil.iter_modules(app.tools.__path__) if module.ispkg}
    modules  = {cls.__module__.split(".")[2] for cls in SOURCES}

    assert packages <= modules


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_source_declares_name_and_query_model(source: type[KnowledgeSource]) -> None:
    """Każde źródło → niepusta `name` i `query_model` będący modelem Pydantica: `ABC` pilnuje
    tylko metod, a bez tych dwóch pól adapter grafu nie zbuduje narzędzia."""
    assert isinstance(getattr(source, "name", None), str) and source.name
    assert issubclass(getattr(source, "query_model", object), BaseModel)


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_query_model_refuses_unknown_arguments(source: type[KnowledgeSource]) -> None:
    """Każdy `query_model` → `extra="forbid"`: model wymyślający argumenty ma dostać błąd, a nie
    zostać po cichu zignorowany."""
    assert source.query_model.model_config.get("extra") == "forbid"


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_source_names_its_material(source: type[KnowledgeSource]) -> None:
    """Każde źródło → niepusta `source` inna niż `name`: na listę źródeł trafia nazwa materiału,
    więc to samo zgłoszenie znalezione dwoma narzędziami jest na niej raz."""
    assert isinstance(getattr(source, "source", None), str) and source.source
    assert source.source != source.name


def test_real_and_fake_of_one_tool_share_a_material() -> None:
    """Materiał → jeden na pakiet narzędzia: źródła z atrapy i z prawdziwego narzędzia mają ten
    sam klucz, inaczej test na atrapie sprawdzałby inną listę źródeł niż produkcja."""
    materials_per_package: dict[str, set[str]] = {}

    for source in SOURCES:
        package = source.__module__.split(".")[2]
        materials_per_package.setdefault(package, set()).add(source.source)

    assert all(len(materials) == 1 for materials in materials_per_package.values())


def test_real_and_fake_of_one_tool_share_a_name_and_no_two_tools_do() -> None:
    """Nazwy → jedna na pakiet narzędzia: atrapa i prawdziwe narzędzie przedstawiają się
    modelowi tak samo, a dwa różne narzędzia nigdy."""
    names_per_package: dict[str, set[str]] = {}

    for source in SOURCES:
        package = source.__module__.split(".")[2]
        names_per_package.setdefault(package, set()).add(source.name)

    assert all(len(names) == 1 for names in names_per_package.values())

    all_names = [next(iter(names)) for names in names_per_package.values()]
    assert len(all_names) == len(set(all_names))
