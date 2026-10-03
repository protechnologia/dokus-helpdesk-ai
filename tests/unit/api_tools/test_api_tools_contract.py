import importlib
import pkgutil

import pytest
from pydantic import BaseModel

import app.tools
from app.tools import AuxiliaryTool, KnowledgeSource


def tool_packages() -> list[str]:
    """
    Description:
    Pakiety narzędzi: te pakiety w `app/tools/`, które nie mają już podpakietów. Folder materiału
    (`tickets/`, `docs/`) sam narzędziem nie jest.

    Example args:
        (brak)

    Example result:
        ["app.tools.docs.find_docs_text", …, "app.tools.tickets.find_tickets_vector"]
    """
    walked   = pkgutil.walk_packages(app.tools.__path__, prefix="app.tools.")
    packages = [module.name for module in walked if module.ispkg]

    leaves = [
        name for name in packages
        if not any(other.startswith(f"{name}.") for other in packages)
    ]

    return leaves


def package_of(
    tool: type,  # np. FakeFindDocsTextTool
) -> str:
    """
    Description:
    Pakiet narzędzia, do którego należy klasa — katalog, w którym leży jej moduł.

    Example args:
        tool=FakeFindDocsTextTool

    Example result:
        "app.tools.docs.find_docs_text"
    """
    return tool.__module__.rsplit(".", 1)[0]


def all_tools_of(
    kind: type,  # KnowledgeSource albo AuxiliaryTool
) -> list[type]:
    """
    Description:
    Zbiera wszystkie klasy narzędzi danego rodzaju z pakietów w `app/tools/`, na każdej
    głębokości — także te, których jeszcze nie ma. Nowe narzędzie to nowy katalog w folderze
    materiału, więc test ma je znaleźć sam, bez dopisywania do listy.

    Example args:
        kind=KnowledgeSource

    Example result:
        [FindTicketsVectorToolBase, FakeFindTicketsVectorTool, FindTicketsVectorTool, …]
    """
    for name in tool_packages():
        importlib.import_module(name)

    found:   list[type] = []
    pending: list[type] = list(kind.__subclasses__())

    while pending:
        cls = pending.pop()
        found.append(cls)
        pending.extend(cls.__subclasses__())

    return found


SOURCES   = all_tools_of(KnowledgeSource)
AUXILIARY = all_tools_of(AuxiliaryTool)
TOOLS     = [*SOURCES, *AUXILIARY]


def arguments_model(
    tool: type,  # np. FakeFindTicketsVectorTool albo FakeListDocsTool
) -> type[BaseModel]:
    """
    Description:
    Model argumentów narzędzia — oba rodzaje trzymają go pod inną nazwą.

    Example args:
        tool=FakeListDocsTool

    Example result:
        ListDocsArgs
    """
    return tool.query_model if issubclass(tool, KnowledgeSource) else tool.args_model


def test_every_tool_package_brings_a_tool() -> None:
    """Pakiety narzędzi → co najmniej jedno narzędzie na pakiet: pusty katalog narzędzia oznacza,
    że importy w jego `__init__.py` coś pominęły."""
    assert set(tool_packages()) <= {package_of(cls) for cls in TOOLS}


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_source_declares_name_and_query_model(source: type[KnowledgeSource]) -> None:
    """Każde źródło → niepusta `name` i `query_model` będący modelem Pydantica: `ABC` pilnuje
    tylko metod, a bez tych dwóch pól adapter grafu nie zbuduje narzędzia."""
    assert isinstance(getattr(source, "name", None), str) and source.name
    assert issubclass(getattr(source, "query_model", object), BaseModel)


@pytest.mark.parametrize("tool", AUXILIARY, ids=lambda cls: cls.__name__)
def test_every_auxiliary_tool_declares_name_and_args_model(tool: type[AuxiliaryTool]) -> None:
    """Każde narzędzie pomocnicze → niepusta `name` i `args_model` będący modelem Pydantica, jak
    `query_model` u źródeł wiedzy."""
    assert isinstance(getattr(tool, "name", None), str) and tool.name
    assert issubclass(getattr(tool, "args_model", object), BaseModel)


@pytest.mark.parametrize("tool", AUXILIARY, ids=lambda cls: cls.__name__)
def test_an_auxiliary_tool_has_nothing_to_cite_with(tool: type[AuxiliaryTool]) -> None:
    """Każde narzędzie pomocnicze → bez `cite()` i bez `source`: jego wynik nie ma jak trafić na
    listę źródeł, i ma tak zostać z samej konstrukcji."""
    assert not hasattr(tool, "cite")
    assert not hasattr(tool, "source")


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_arguments_model_refuses_unknown_arguments(tool: type) -> None:
    """Każdy model argumentów → `extra="forbid"`: model wymyślający argumenty ma dostać błąd,
    a nie zostać po cichu zignorowany."""
    assert arguments_model(tool).model_config.get("extra") == "forbid"


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
        package = package_of(source)
        materials_per_package.setdefault(package, set()).add(source.source)

    assert all(len(materials) == 1 for materials in materials_per_package.values())


def test_real_and_fake_of_one_tool_share_a_name_and_no_two_tools_do() -> None:
    """Nazwy → jedna na pakiet narzędzia: atrapa i prawdziwe narzędzie przedstawiają się
    modelowi tak samo, a dwa różne narzędzia nigdy."""
    names_per_package: dict[str, set[str]] = {}

    for tool in TOOLS:
        package = package_of(tool)
        names_per_package.setdefault(package, set()).add(tool.name)

    assert all(len(names) == 1 for names in names_per_package.values())

    all_names = [next(iter(names)) for names in names_per_package.values()]
    assert len(all_names) == len(set(all_names))
