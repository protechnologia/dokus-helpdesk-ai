import json
from datetime import date
from pathlib import Path

import pytest

from app.core_service.loader_code_description import CodeDescription
from app.core_service.loader_code_package import CodePackageConfigError

# Opis projektu i metryczka stoją w katalogu paczki obok `repo/`. Testy zakładają oba pliki
# w katalogu tymczasowym, więc nie potrzebują paczki zbudowanej skryptem.

TEXT = "Aplikacja urzędu: backend w `src/lib/`, interfejs w `src/web/js/`."


def _description(
    tmp_path: Path,                                # katalog tymczasowy testu
    text:     str | bytes | None = TEXT,           # treść `project.md`; None: pliku nie ma
    manifest: object = None,                       # treść `manifest.json`; None: pliku nie ma
) -> CodeDescription:
    """
    Description:
    Zakłada katalog paczki z opisem projektu i metryczką o podanej treści i oddaje ich czytnik.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        text="Aplikacja urzędu: backend w `src/lib/`…"
        manifest={"branch": "/main", "built_on": "2026-10-07"}

    Example result:
        CodeDescription czytająca <tmp_path>/paczka/project.md i manifest.json
    """
    root = tmp_path / "paczka"
    root.mkdir()

    if isinstance(text, bytes):
        (root / "project.md").write_bytes(text)
    elif text is not None:
        (root / "project.md").write_text(text, encoding="utf-8")

    if isinstance(manifest, str):
        (root / "manifest.json").write_text(manifest, encoding="utf-8")
    elif manifest is not None:
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return CodeDescription(root)


def test_the_description_comes_back_whole_without_editorial_comments(tmp_path: Path) -> None:
    """Sprawdza, czy opis projektu wraca w całości, znak w znak, ale bez komentarza
    redakcyjnego z początku pliku i bez pustych linii na brzegach.

    Wyłapuje opis oddawany razem z notatką dla nas („szkic, niezatwierdzony"): trafiłaby do
    modelu jako część opisu aplikacji."""
    text = f"<!-- szkic, niezatwierdzony -->\n\n{TEXT}\n\nDruga linia.\n\n"

    assert _description(tmp_path, text).read_text() == f"{TEXT}\n\nDruga linia."


def test_a_description_changed_on_disk_is_read_again(tmp_path: Path) -> None:
    """Sprawdza, czy po zmianie pliku opisu ten sam czytnik oddaje już nową treść.

    Wyłapuje czytnik, który pamięta opis od pierwszego odczytu: opis poprawia się bez restartu
    usługi, więc model dostawałby starą wersję aż do następnego uruchomienia."""
    description = _description(tmp_path)

    before = description.read_text()
    (tmp_path / "paczka" / "project.md").write_text("Nowy opis.", encoding="utf-8")

    assert (before, description.read_text()) == (TEXT, "Nowy opis.")


@pytest.mark.parametrize(
    "text",
    [None, "", "  \n\n", "<!-- sam komentarz -->\n", b"\xff\xfe opis w innym kodowaniu"],
    ids=["brak pliku", "pusty plik", "same białe znaki", "sam komentarz", "nie UTF-8"],
)
def test_a_missing_or_empty_description_is_a_configuration_error(
    tmp_path: Path,
    text:     str | bytes | None,
) -> None:
    """Sprawdza, czy brak pliku opisu, plik pusty, plik z samymi białymi znakami, z samym
    komentarzem redakcyjnym albo w kodowaniu innym niż UTF-8 kończy się wyjątkiem
    `CodePackageConfigError`.

    Wyłapuje czytnik, który w takim przypadku oddaje pusty tekst: model dostałby opis, w którym
    nic nie ma, szukałby dalej bez niego i nikt nie dowiedziałby się, że paczka jest
    niekompletna."""
    with pytest.raises(CodePackageConfigError):
        _description(tmp_path, text).read_text()


def test_the_branch_and_the_build_day_come_from_the_manifest(tmp_path: Path) -> None:
    """Sprawdza, czy z metryczki paczki wracają gałąź i dzień budowy, a pozostałe jej pola
    (źródło, liczby plików) nie przeszkadzają w odczycie.

    Wyłapuje czytnik, który bierze inną wartość z metryczki albo wymaga, żeby miała tylko te
    dwa pola: prawdziwa metryczka niesie też listę pominiętych plików."""
    manifest = {
        "source":   "/mnt/c/kod",
        "branch":   "/main/stage-gminy",
        "built_on": "2026-10-07",
        "package":  {"files": 3},
    }

    info = _description(tmp_path, manifest=manifest).read_package_info()

    assert (info.branch, info.built_on) == ("/main/stage-gminy", date(2026, 10, 7))


def test_a_manifest_without_a_branch_gives_no_branch(tmp_path: Path) -> None:
    """Sprawdza, czy metryczka z gałęzią zapisaną jako `null` (paczka z folderu, który nie jest
    kopią roboczą) daje brak gałęzi, a nie błąd.

    Wyłapuje czytnik, który wymaga gałęzi: paczka z aplikacji syntetycznej jej nie ma, więc
    żadne narzędzie stojące na metryczce by na niej nie działało."""
    info = _description(tmp_path, manifest={"branch": None, "built_on": "2026-10-11"})

    assert info.read_package_info().branch is None


@pytest.mark.parametrize(
    "manifest",
    [
        None,
        "to nie jest JSON",
        {"built_on": "2026-10-07"},
        {"branch": "/main"},
        {"branch": "", "built_on": "2026-10-07"},
        {"branch": "/main", "built_on": "wczoraj"},
        ["/main", "2026-10-07"],
    ],
    ids=["brak pliku", "nie JSON", "bez gałęzi", "bez dnia", "pusta gałąź", "zła data", "lista"],
)
def test_an_unreadable_manifest_is_a_configuration_error(
    tmp_path: Path,
    manifest: object,
) -> None:
    """Sprawdza, czy brak metryczki, plik, który nie jest JSON-em, metryczka bez gałęzi albo bez
    dnia budowy, z pustą gałęzią, ze złą datą albo zapisana jako lista kończy się wyjątkiem
    `CodePackageConfigError`.

    Wyłapuje czytnik, który z niepełnej metryczki oddaje brak gałęzi: źródło z kodu nie
    mówiłoby wtedy, z której wersji kodu pochodzi, choć paczka po prostu nie powstała
    skryptem albo skrypt zmienił kształt metryczki."""
    with pytest.raises(CodePackageConfigError):
        _description(tmp_path, manifest=manifest).read_package_info()


def test_the_error_names_the_file_that_is_missing(tmp_path: Path) -> None:
    """Sprawdza, czy komunikat błędu przy braku opisu podaje ścieżkę pliku `project.md`,
    a przy braku metryczki ścieżkę pliku `manifest.json`.

    Wyłapuje komunikat bez nazwy pliku: błąd trafia do logu usługi i ma mówić wdrażającemu,
    którego pliku w paczce brakuje, bez czytania kodu."""
    description = _description(tmp_path, text=None)

    with pytest.raises(CodePackageConfigError, match="project.md"):
        description.read_text()

    with pytest.raises(CodePackageConfigError, match="manifest.json"):
        description.read_package_info()
