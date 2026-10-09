import importlib
import pkgutil
from collections.abc import Callable

import pytest
from pydantic import BaseModel

import app.agent_tools
from app.agent_graphs.base import MAX_CALLS_PLACEHOLDER
from app.agent_tools import AgentTool, AuxiliaryTool, KnowledgeSource, ToolCallError
from app.config import Settings
from tests.helpers_agent_tools import fake_agent_tools, fake_agent_tools_without_material


def tool_packages() -> list[str]:
    """
    Description:
    Pakiety narzędzi: te pakiety w `app/agent_tools/`, które nie mają już podpakietów. Folder
    materiału (`tickets/`, `docs/`) sam narzędziem nie jest.

    Example args:
        (brak)

    Example result:
        ["app.agent_tools.docs.find_docs_text", …, "app.agent_tools.tickets.find_tickets_vector"]
    """
    walked   = pkgutil.walk_packages(app.agent_tools.__path__, prefix="app.agent_tools.")
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
        "app.agent_tools.docs.find_docs_text"
    """
    return tool.__module__.rsplit(".", 1)[0]


def all_tools_of(
    kind: type,  # KnowledgeSource albo AuxiliaryTool
) -> list[type]:
    """
    Description:
    Zbiera wszystkie klasy narzędzi danego rodzaju z pakietów w `app/agent_tools/`, na każdej
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


def tool_errors() -> list[type[Exception]]:
    """
    Description:
    Zbiera klasy wyjątków zdefiniowane w modułach `errors.py` pakietów narzędzi — także tych,
    których jeszcze nie ma.

    Example args:
        (brak)

    Example result:
        [UnknownSectionError, UnknownTicketError]
    """
    found: list[type[Exception]] = []

    for package in tool_packages():
        try:
            module = importlib.import_module(f"{package}.errors")
        except ModuleNotFoundError:  # narzędzie bez własnych błędów
            continue

        found.extend(
            member
            for member in vars(module).values()
            if isinstance(member, type)
            and issubclass(member, Exception)
            and member.__module__ == module.__name__
        )

    return found


SOURCES   = all_tools_of(KnowledgeSource)
AUXILIARY = all_tools_of(AuxiliaryTool)
TOOLS     = [*SOURCES, *AUXILIARY]

# Układ opisu narzędzia (`description.md`), wspólny dla wszystkich narzędzi.
DESCRIPTION_SECTIONS = ["# Do czego służy", "# Jak wywoływać", "# Co zwraca", "# Zasady"]

ERRORS = tool_errors()


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
    """Sprawdza, czy z każdego katalogu narzędzia w `app/agent_tools/` pochodzi co najmniej jedna
    klasa narzędzia.

    Wyłapuje katalog narzędzia, którego `__init__.py` pominął import: takie narzędzie bez żadnego
    sygnału wypadłoby z pozostałych testów tego pliku, bo znajdują one narzędzia wśród
    zaimportowanych klas."""
    assert set(tool_packages()) <= {package_of(cls) for cls in TOOLS}


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_source_declares_name_and_query_model(source: type[KnowledgeSource]) -> None:
    """Sprawdza, czy każde źródło wiedzy, czyli narzędzie odczytu albo cytowania kodu, ma niepustą
    nazwę (`name`) i klasę zapytania (`query_model`) będącą modelem Pydantica.

    Wyłapuje źródło bez jednego z tych pól: `ABC` pilnuje tylko metod, a bez nazwy i klasy zapytania
    graf nie zbuduje definicji narzędzia dla modelu."""
    assert isinstance(getattr(source, "name", None), str) and source.name
    assert issubclass(getattr(source, "query_model", object), BaseModel)


@pytest.mark.parametrize("tool", AUXILIARY, ids=lambda cls: cls.__name__)
def test_every_auxiliary_tool_declares_name_and_args_model(tool: type[AuxiliaryTool]) -> None:
    """Sprawdza, czy każde narzędzie pomocnicze, czyli wyszukiwanie albo spis treści, ma niepustą
    nazwę (`name`) i klasę argumentów (`args_model`) będącą modelem Pydantica.

    Wyłapuje narzędzie pomocnicze bez jednego z tych pól: graf nie zbudowałby z niego definicji
    narzędzia dla modelu, tak samo jak ze źródła wiedzy bez `query_model`."""
    assert isinstance(getattr(tool, "name", None), str) and tool.name
    assert issubclass(getattr(tool, "args_model", object), BaseModel)


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_tool_describes_itself_to_the_model(tool: type) -> None:
    """Sprawdza, czy każde narzędzie ma niepusty opis dla modelu (`description`) i czy w tym opisie
    nie ma komentarza redakcyjnego (`<!--`).

    Wyłapuje narzędzie bez opisu, z którego graf składa definicję dla modelu, oraz notatkę pisaną
    dla nas, która przeszła do tekstu czytanego przez model."""
    assert isinstance(getattr(tool, "description", None), str) and tool.description
    assert "<!--" not in tool.description


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_description_has_the_same_four_sections(tool: type) -> None:
    """Sprawdza, czy opis każdego narzędzia ma dokładnie cztery nagłówki, zawsze w tej kolejności:
    „Do czego służy", „Jak wywoływać", „Co zwraca" i „Zasady".

    Wyłapuje opis ułożony inaczej: model czyta wszystkie opisy naraz i ma w każdym znaleźć
    argumenty, wynik i zasady w tym samym miejscu."""
    headings = [line for line in tool.description.splitlines() if line.startswith("#")]

    assert headings == DESCRIPTION_SECTIONS


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_description_shows_the_result_in_one_table(tool: type) -> None:
    """Sprawdza, czy w opisie każdego narzędzia sekcja „Co zwraca" zawiera dokładnie jedną tabelkę.

    Wyłapuje opis bez tabelki wyniku albo z drugą tabelką na pola zagnieżdżone: mają one stać
    w jednej tabelce pod pełną ścieżką (`sections[].section.title`), inaczej model musiałby sam
    dopasować jedną tabelkę do drugiej."""
    returns    = tool.description.split("# Co zwraca")[1].split("# Zasady")[0]
    separators = [line for line in returns.splitlines() if line.startswith("|-")]

    assert len(separators) == 1


@pytest.mark.parametrize("tool", AUXILIARY, ids=lambda cls: cls.__name__)
def test_an_auxiliary_tool_has_nothing_to_cite_with(tool: type[AuxiliaryTool]) -> None:
    """Sprawdza, czy żadne narzędzie pomocnicze nie ma metody `cite()` ani pola `source`.

    Wyłapuje wyszukiwanie albo spis treści, które dostały sposób na dopisanie czegoś do listy
    źródeł: źródłem ma być tylko to, co model przeczytał, a nie to, co znalazł."""
    assert not hasattr(tool, "cite")
    assert not hasattr(tool, "source")


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_arguments_model_refuses_unknown_arguments(tool: type) -> None:
    """Sprawdza, czy klasa argumentów każdego narzędzia odrzuca nieznane pola (`extra="forbid"`).

    Wyłapuje narzędzie, które po cichu pomija argument wymyślony przez model: model ma dostać błąd,
    a nie zostać zignorowany bez słowa."""
    assert arguments_model(tool).model_config.get("extra") == "forbid"


@pytest.mark.parametrize("source", SOURCES, ids=lambda cls: cls.__name__)
def test_every_source_names_its_material(source: type[KnowledgeSource]) -> None:
    """Sprawdza, czy każde źródło wiedzy ma niepustą nazwę materiału (`source`), inną niż nazwa
    samego narzędzia.

    Wyłapuje źródło podpisane nazwą narzędzia zamiast materiału: to samo zgłoszenie odczytane dwoma
    narzędziami stałoby wtedy na liście źródeł dwa razy."""
    assert isinstance(getattr(source, "source", None), str) and source.source
    assert source.source != source.name


def test_real_and_fake_of_one_tool_share_a_material() -> None:
    """Sprawdza, czy prawdziwe narzędzie i jego atrapa, czyli wszystkie źródła wiedzy z jednego
    katalogu narzędzia, mają tę samą nazwę materiału.

    Wyłapuje atrapę podpisującą źródła innym materiałem niż prawdziwe narzędzie: test na atrapie
    sprawdzałby wtedy inną listę źródeł niż ta, która powstaje na produkcji."""
    materials_per_package: dict[str, set[str]] = {}

    for source in SOURCES:
        package = package_of(source)
        materials_per_package.setdefault(package, set()).add(source.source)

    assert all(len(materials) == 1 for materials in materials_per_package.values())


def test_real_and_fake_of_one_tool_share_a_name_and_no_two_tools_do() -> None:
    """Sprawdza, czy prawdziwe narzędzie i jego atrapa mają jedną nazwę i czy żadne dwa różne
    narzędzia nie mają tej samej.

    Wyłapuje atrapę, która przedstawia się modelowi inaczej niż prawdziwe narzędzie, oraz dwa
    narzędzia pod jedną nazwą, których model nie mógłby rozróżnić przy wywołaniu."""
    names_per_package: dict[str, set[str]] = {}

    for tool in TOOLS:
        package = package_of(tool)
        names_per_package.setdefault(package, set()).add(tool.name)

    assert all(len(names) == 1 for names in names_per_package.values())

    all_names = [next(iter(names)) for names in names_per_package.values()]
    assert len(all_names) == len(set(all_names))


@pytest.mark.parametrize("tool", TOOLS, ids=lambda cls: cls.__name__)
def test_every_description_has_one_place_for_the_call_limit(tool: type) -> None:
    """Sprawdza, czy opis każdego narzędzia ma dokładnie jedno miejsce na limit wywołań
    (`{{max_calls}}`).

    Wyłapuje opis bez tego miejsca albo z dwoma: graf wpisuje w nie wartość z konfiguracji i tylko
    stąd model zna limit z góry."""
    assert tool.description.count(MAX_CALLS_PLACEHOLDER) == 1


def test_every_tool_has_a_call_limit_in_the_configuration() -> None:
    """Sprawdza, czy konfiguracja (`Settings`) ma limit wywołań dla każdego narzędzia i dla niczego
    poza narzędziami: nazwy z limitów i nazwy narzędzi to ten sam zbiór.

    Wyłapuje rozjazd w obie strony: nowe narzędzie bez pola `agent_max_calls_<narzędzie>` nie
    złożyłoby definicji dla modelu, a pole bez narzędzia byłoby martwą zmienną w `.env`."""
    limits = Settings(_env_file=None).tool_call_limits()

    assert set(limits) == {tool.name for tool in TOOLS}


@pytest.mark.parametrize(
    "helper",
    [fake_agent_tools, fake_agent_tools_without_material],
    ids=lambda helper: helper.__name__,
)
def test_the_test_helper_has_one_fake_of_every_tool(
    helper: Callable[[], list[AgentTool]],
) -> None:
    """Sprawdza, czy każdy z dwóch helperów z kompletem atrap narzędzi (`fake_agent_tools()`
    i `fake_agent_tools_without_material()`) oddaje dokładnie jedną atrapę na każde narzędzie
    znalezione w `app/agent_tools/`.

    Wyłapuje nowe narzędzie, o którym helper nie wie: testy węzłów, grafów i tras biorą komplet
    atrap z tego jednego miejsca, więc bez wpisu przechodziłyby dalej, tylko bez nowego narzędzia,
    i nikt by tego nie zauważył."""
    names = [tool.name for tool in helper()]

    assert sorted(names) == sorted({tool.name for tool in TOOLS})


def test_some_tool_brings_its_own_errors() -> None:
    """Sprawdza, czy zbieranie błędów własnych narzędzi cokolwiek znajduje: dziś mają je odczyt
    wątku, odczyt sekcji dokumentacji i cytowanie kodu.

    Wyłapuje zbieranie, które po zmianie układu katalogów nie widzi żadnego modułu `errors.py`:
    test niżej przechodziłby wtedy na pustej liście i niczego nie sprawdzał."""
    assert len(ERRORS) >= 2


@pytest.mark.parametrize("error", ERRORS, ids=lambda cls: cls.__name__)
def test_every_error_of_a_tool_goes_back_to_the_model(error: type[Exception]) -> None:
    """Sprawdza, czy każdy błąd zdefiniowany przez narzędzie w jego `errors.py` jest odmianą
    `ToolCallError`.

    Wyłapuje nowy błąd narzędzia poza tą rodziną: węzeł wykonujący narzędzia nie oddałby go
    modelowi do poprawienia, tylko przerwał całe żądanie błędem serwera."""
    assert issubclass(error, ToolCallError)
