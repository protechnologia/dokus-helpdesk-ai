import json
from datetime import date
from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.describe_code import DescribeCodeQuery, DescribeCodeTool
from app.core_service.loader_code_description import CodeDescription
from app.core_service.loader_code_package import CodePackageConfigError

# Narzędzie stoi na prawdziwym czytniku opisu projektu, a paczka to dwa pliki w katalogu
# tymczasowym — sprawdzamy więc, co narzędzie składa z opisu i metryczki i co robi, gdy
# któregoś brakuje. Sam odczyt plików sprawdzają testy czytnika; paczkę syntetyczną czyta test
# integracyjny.

TEXT = "## Części\n\nBackend w `src/lib/`.\n\n## Czego w paczce nie ma\n\nStylów."


def _tool(
    tmp_path:    Path,                 # katalog tymczasowy testu
    text:        str | None = TEXT,    # treść `project.md`; None: pliku nie ma
    branch:      str | None = "/main",  # gałąź w metryczce
    manifest:    bool = True,          # False: paczka bez metryczki
) -> DescribeCodeTool:
    """
    Description:
    Buduje narzędzie na katalogu paczki z opisem projektu i metryczką o podanej treści.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        text="## Części\\n\\nBackend w `src/lib/`.…"
        branch="/main"
        manifest=True

    Example result:
        DescribeCodeTool czytające <tmp_path>/paczka/project.md i manifest.json
    """
    root = tmp_path / "paczka"
    root.mkdir()

    if text is not None:
        (root / "project.md").write_text(text, encoding="utf-8")

    if manifest:
        metadata = {"branch": branch, "built_on": "2026-10-07"}
        (root / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")

    return DescribeCodeTool(description=CodeDescription(root))


async def test_the_description_comes_back_whole_with_the_branch_of_the_package(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy narzędzie oddaje opis projektu w całości, z nagłówkami i odstępami, oraz
    gałąź i dzień budowy z metryczki paczki.

    Wyłapuje narzędzie, które opis skraca albo gubi metryczkę: model nie wiedziałby, z której
    gałęzi pochodzi kod, który czyta, a klienci mają własne gałęzie."""
    result = await _tool(tmp_path).describe()

    assert result.description           == TEXT
    assert result.package_info.branch   == "/main"
    assert result.package_info.built_on == date(2026, 10, 7)


async def test_the_model_reads_the_description_as_json(tmp_path: Path) -> None:
    """Sprawdza, czy tekst dla modelu to JSON z metryczką paczki i opisem, w którym znaki nowej
    linii z opisu wracają po odczytaniu JSON-a bez zmian, a gałąź nieznana paczce to `null`.

    Wyłapuje tekst dla modelu składany ręcznie zamiast z wyniku: opis z cudzysłowem albo nową
    linią rozsypałby JSON, a brak gałęzi wyszedłby jako napis „None"."""
    body = json.loads(await _tool(tmp_path, branch=None).run(DescribeCodeQuery()))

    assert body == {
        "package_info": {"branch": None, "built_on": "2026-10-07"},
        "description":  TEXT,
    }


async def test_an_editorial_comment_of_the_description_stays_with_us(tmp_path: Path) -> None:
    """Sprawdza, czy komentarz redakcyjny z pliku opisu nie trafia do wyniku narzędzia.

    Wyłapuje notatkę „szkic, do poprawienia przez programistę" oddaną modelowi jako część
    opisu aplikacji."""
    tool = _tool(tmp_path, text=f"<!-- szkic, do poprawienia -->\n{TEXT}\n")

    result = await tool.describe()

    assert result.description == TEXT
    assert "szkic" not in await tool.run(DescribeCodeQuery())


async def test_a_description_corrected_on_disk_is_served_at_once(tmp_path: Path) -> None:
    """Sprawdza, czy po poprawieniu pliku opisu to samo narzędzie oddaje już nową treść.

    Wyłapuje narzędzie, które pamięta opis od pierwszego wywołania: programista poprawia opis
    bez restartu usługi, a model dostawałby starą wersję."""
    tool = _tool(tmp_path)

    before = (await tool.describe()).description
    (tmp_path / "paczka" / "project.md").write_text("Poprawiony opis.", encoding="utf-8")

    assert (before, (await tool.describe()).description) == (TEXT, "Poprawiony opis.")


@pytest.mark.parametrize(
    ("text", "manifest"),
    [(None, True), ("", True), (TEXT, False)],
    ids=["brak opisu", "pusty opis", "brak metryczki"],
)
async def test_an_incomplete_package_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
    text:     str | None,
    manifest: bool,
) -> None:
    """Sprawdza, czy wywołanie na paczce bez opisu projektu, z pustym opisem albo bez metryczki
    kończy się wyjątkiem `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak opisu oddawany modelowi jako błąd narzędzia: model szukałby dalej bez opisu,
    sprawa skończyłaby się zwykłą odpowiedzią i nikt nie dowiedziałby się, że paczce brakuje
    pliku."""
    tool = _tool(tmp_path, text=text, manifest=manifest)

    with pytest.raises(CodePackageConfigError) as caught:
        await tool.describe()

    assert not isinstance(caught.value, ToolCallError)
