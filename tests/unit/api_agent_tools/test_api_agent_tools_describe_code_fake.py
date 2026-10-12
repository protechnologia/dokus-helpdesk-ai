import json
import re

from app.agent_tools.code.describe_code import DescribeCodeQuery, FakeDescribeCodeTool
from app.agent_tools.code.fake_code import (
    BACKEND_DIR,
    INTERFACE_DIR,
    PACKAGE_BUILT_ON,
    PROJECT_DESCRIPTION,
)
from app.agent_tools.code.list_code_files import FakeListCodeFilesTool, ListCodeFilesQuery
from app.core_model.code.code_package_info import CodePackageInfo

# Ścieżka w opisie projektu: napis w odwróconych apostrofach zaczynający się od `src/`.
PATH_IN_DESCRIPTION = re.compile(r"`(src/[^`]*)`")


async def test_the_fake_returns_the_built_in_description_without_a_branch() -> None:
    """Sprawdza, czy atrapa bez argumentów oddaje wbudowany opis zmyślonej aplikacji i metryczkę
    bez gałęzi, ze stałym dniem budowy.

    Wyłapuje atrapę z gałęzią wpisaną na stałe: tytuły źródeł z kodu w testach grafów
    dostałyby dopisek, którego paczka z aplikacji syntetycznej nie daje."""
    result = await FakeDescribeCodeTool().describe()

    assert result.description  == PROJECT_DESCRIPTION
    assert result.package_info == CodePackageInfo(branch=None, built_on=PACKAGE_BUILT_ON)


async def test_the_model_reads_the_result_as_json_with_the_info_and_the_text() -> None:
    """Sprawdza, czy tekst, który model dostaje od atrapy, to JSON z dwiema częściami: metryczką
    paczki (gałąź równa `null` i dzień budowy jako data) oraz opisem projektu.

    Wyłapuje atrapę z własnym kształtem tekstu dla modelu: test grafu na atrapie sprawdzałby
    wtedy inny tekst niż ten, który model czyta na produkcji."""
    body = json.loads(await FakeDescribeCodeTool().run(DescribeCodeQuery()))

    assert set(body)            == {"package_info", "description"}
    assert body["package_info"] == {"branch": None, "built_on": PACKAGE_BUILT_ON.isoformat()}
    assert body["description"]  == PROJECT_DESCRIPTION


async def test_the_fake_takes_its_own_description_and_branch() -> None:
    """Sprawdza, czy atrapa zbudowana z własnym opisem i własną metryczką oddaje właśnie je.

    Wyłapuje atrapę, która zawsze oddaje zestaw wbudowany: nie dałoby się odtworzyć sprawy na
    paczce z gałęzią ani sprawy, w której opis nie wymienia żadnego katalogu."""
    info = CodePackageInfo(branch="/main/stage-gminy", built_on="2026-10-07")
    tool = FakeDescribeCodeTool(description="Aplikacja bez katalogów.", package_info=info)

    result = await tool.describe()

    assert (result.description, result.package_info) == ("Aplikacja bez katalogów.", info)


async def test_every_call_is_counted() -> None:
    """Sprawdza, czy atrapa liczy wywołania: po dwóch odczytach opisu licznik `calls` wynosi 2.

    Wyłapuje atrapę bez licznika: test grafu nie miałby jak sprawdzić, czy i ile razy agent
    sięgnął po opis projektu."""
    tool = FakeDescribeCodeTool()

    await tool.describe()
    await tool.run(DescribeCodeQuery())

    assert tool.calls == 2


async def test_the_directories_of_the_description_exist_for_the_listing_fake() -> None:
    """Sprawdza, czy każdy katalog wymieniony we wbudowanym opisie projektu atrapa spisu
    katalogu potrafi spisać, i czy opis wymienia katalogi obu zmyślonych plików.

    Wyłapuje opis rozjechany z resztą atrap kodu: model w teście grafu brałby z opisu katalog
    i dostawał od spisu błąd, choć na produkcji opis i spis mówią o tej samej paczce."""
    listing = FakeListCodeFilesTool()
    named   = PATH_IN_DESCRIPTION.findall(PROJECT_DESCRIPTION)

    assert f"{BACKEND_DIR}/" in named and f"{INTERFACE_DIR}/" in named

    for path in named:
        result = await listing.list_dir(ListCodeFilesQuery(path=path, depth=9))

        assert result.entries, path
