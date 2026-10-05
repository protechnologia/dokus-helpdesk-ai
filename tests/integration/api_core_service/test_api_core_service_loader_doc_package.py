import json
from pathlib import Path

import pytest

from app.core_service import loader_doc_package
from app.core_service.loader_doc_package import load_doc_package

# Czytnik paczki na prawdziwych plikach: paczki zmyślone w `tmp_path` i paczka syntetyczna z repo.

REPO_ROOT         = Path(__file__).resolve().parents[3]
SYNTHETIC_PACKAGE = REPO_ROOT / "data" / "safe" / "instruction"
SYNTHETIC_GOLDEN  = REPO_ROOT / "data" / "safe" / "golden" / "docs-synthetic.json"


def _write_document(
    root:        Path,                          # np. tmp_path
    name:        str,                           # nazwa katalogu dokumentu, np. "administrator"
    section_ids: tuple[str, ...] = ("wstep",),  # sekcje w manifeście; każda dostaje plik
    **manifest:  object,                        # nadpisania nagłówka, np. synthetic=True
) -> Path:
    """
    Description:
    Zakłada katalog jednego dokumentu: manifest z podanymi sekcjami i plik `.md` na każdą.

    Example args:
        root=Path("/tmp/x")
        name="administrator"
        section_ids=("wstep", "uprawnienia")
        manifest={"synthetic": True}

    Example result:
        Path("/tmp/x/administrator") z manifest.json, wstep.md i uprawnienia.md
    """
    directory = root / name
    directory.mkdir()

    payload = {
        "document":  f"Instrukcja {name}",
        "version":   "4.12",
        "date":      "2026-05-04",
        "synthetic": False,
        "sections":  [
            {
                "section_id":   section_id,
                "chapter_path": ["Rozdział"],
                "title":        f"Tytuł {section_id}",
                "description":  f"Opis {section_id}",
            }
            for section_id in section_ids
        ],
        **manifest,
    }

    (directory / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    for section_id in section_ids:
        (directory / f"{section_id}.md").write_text(f"Treść sekcji {section_id}.\n", "utf-8")

    return directory


# --- poprawna paczka ----------------------------------------------------------------------

def test_a_valid_package_is_read_with_its_bodies(tmp_path: Path) -> None:
    """Dokument z dwiema sekcjami → manifest, treść obu plików i brak uwag."""
    _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))

    package   = load_doc_package(tmp_path)
    directory = package.directories[0]

    assert package.ok
    assert package.section_count       == 2
    assert directory.manifest.document == "Instrukcja administrator"
    assert directory.bodies            == {
        "wstep":       "Treść sekcji wstep.\n",
        "uprawnienia": "Treść sekcji uprawnienia.\n",
    }


def test_documents_come_in_directory_name_order(tmp_path: Path) -> None:
    """Dwa dokumenty → w kolejności nazw katalogów, żeby dwa przebiegi dawały ten sam raport."""
    _write_document(tmp_path, "uzytkownik", ("b",))
    _write_document(tmp_path, "administrator", ("a",))

    package = load_doc_package(tmp_path)

    assert [directory.path.name for directory in package.directories] == [
        "administrator",
        "uzytkownik",
    ]


def test_the_body_is_kept_verbatim(tmp_path: Path) -> None:
    """Treść z wcięciem i pustymi liniami na brzegach → wraca znak w znak: w tej postaci idzie
    do bazy i do agenta."""
    directory = _write_document(tmp_path, "administrator")
    body      = "\n  Uprawnienie nadaje administrator.\n\n- pozycja\n\n"

    (directory / "wstep.md").write_text(body, encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].bodies["wstep"] == body


def test_an_empty_root_is_a_valid_empty_package(tmp_path: Path) -> None:
    """Pusty katalog → pusta, poprawna paczka: katalog właściwej dokumentacji bywa pusty."""
    package = load_doc_package(tmp_path)

    assert package.ok
    assert package.directories == []


def test_hidden_directories_and_loose_files_are_not_documents(tmp_path: Path) -> None:
    """Katalog ukryty i plik luzem obok dokumentów → pominięte bez błędu."""
    _write_document(tmp_path, "administrator")
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Notatka o paczce.", encoding="utf-8")

    package = load_doc_package(tmp_path)

    assert package.ok
    assert [directory.path.name for directory in package.directories] == ["administrator"]


# --- zły katalog --------------------------------------------------------------------------

def test_a_missing_root_is_an_error(tmp_path: Path) -> None:
    """Ścieżka, która nie jest katalogiem → NotADirectoryError, nigdy pusta paczka."""
    with pytest.raises(NotADirectoryError):
        load_doc_package(tmp_path / "nie-ma")


def test_a_document_directory_given_as_the_package_is_refused(tmp_path: Path) -> None:
    """Wskazany katalog jednego dokumentu → błąd paczki mówiący, żeby podać katalog nadrzędny;
    inaczej paczka wyglądałaby na pustą."""
    directory = _write_document(tmp_path, "administrator")

    package = load_doc_package(directory)

    assert not package.ok
    assert "katalog nadrzędny" in package.errors[0]


# --- manifest -----------------------------------------------------------------------------

def test_a_directory_without_a_manifest_is_reported(tmp_path: Path) -> None:
    """Podkatalog bez `manifest.json` → błąd tego katalogu, nie ciche pominięcie."""
    (tmp_path / "administrator").mkdir()

    directory = load_doc_package(tmp_path).directories[0]

    assert directory.manifest is None
    assert directory.errors   == ["brak pliku manifest.json"]


def test_a_manifest_that_is_not_json_is_reported(tmp_path: Path) -> None:
    """Manifest z zepsutym JSON-em → błąd katalogu nazywający plik."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "manifest.json").write_text("{nie json", encoding="utf-8")

    errors = load_doc_package(tmp_path).directories[0].errors

    assert len(errors) == 1
    assert errors[0].startswith("manifest.json: ")


def test_a_manifest_outside_the_contract_names_the_field(tmp_path: Path) -> None:
    """Manifest bez wydania i z kluczem spoza kontraktu → osobna linia na każde pole."""
    _write_document(tmp_path, "administrator", version="", author="Jan Kowalski")

    errors = load_doc_package(tmp_path).directories[0].errors

    assert any("version" in error for error in errors)
    assert any("author" in error for error in errors)


# --- zgodność manifestu z katalogiem ------------------------------------------------------

def test_a_section_without_its_file_is_reported(tmp_path: Path) -> None:
    """Sekcja z manifestu bez pliku `.md` → błąd nazywający plik."""
    directory = _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))
    (directory / "uprawnienia.md").unlink()

    loaded = load_doc_package(tmp_path).directories[0]

    assert loaded.errors == ["brak pliku uprawnienia.md"]
    assert set(loaded.bodies) == {"wstep"}


def test_a_file_without_a_manifest_entry_is_reported(tmp_path: Path) -> None:
    """Plik `.md` bez wpisu w manifeście → błąd: taka sekcja nie trafiłaby do indeksu i nic by
    tego nie zgłosiło."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "nowa-sekcja.md").write_text("Treść bez wpisu.", encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].errors == [
        "plik bez wpisu w manifeście: nowa-sekcja.md"
    ]


@pytest.mark.parametrize("content", ["", "  \n\n"])
def test_an_empty_section_file_is_reported(tmp_path: Path, content: str) -> None:
    """Plik sekcji bez treści → błąd: sekcja bez tekstu niczego nie opisuje."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").write_text(content, encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].errors == ["wstep.md jest pusty"]


def test_a_section_file_that_is_not_utf8_is_reported(tmp_path: Path) -> None:
    """Plik sekcji w innym kodowaniu → błąd nazywający plik, a nie wyjątek przerywający
    przebieg."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").write_bytes("Treść sekcji".encode("cp1250"))

    errors = load_doc_package(tmp_path).directories[0].errors

    assert len(errors) == 1
    assert errors[0].startswith("wstep.md nie jest tekstem UTF-8")


def test_every_problem_of_a_directory_is_reported_at_once(tmp_path: Path) -> None:
    """Brak pliku, pusty plik i plik bez wpisu naraz → trzy błędy w jednym przebiegu."""
    directory = _write_document(tmp_path, "administrator", ("a", "b", "c"))

    (directory / "a.md").unlink()
    (directory / "b.md").write_text("", encoding="utf-8")
    (directory / "d.md").write_text("Treść bez wpisu.", encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].errors == [
        "brak pliku a.md",
        "b.md jest pusty",
        "plik bez wpisu w manifeście: d.md",
    ]


def test_one_broken_document_does_not_hide_the_others(tmp_path: Path) -> None:
    """Jeden katalog zły, drugi dobry → paczka niepoprawna, ale dobry dokument jest wczytany."""
    _write_document(tmp_path, "administrator")
    (tmp_path / "uzytkownik").mkdir()

    package = load_doc_package(tmp_path)

    assert not package.ok
    assert [directory.ok for directory in package.directories] == [True, False]


# --- ponad dokumentami --------------------------------------------------------------------

def test_the_same_section_id_in_two_documents_is_a_package_error(tmp_path: Path) -> None:
    """Ten sam `section_id` w dwóch dokumentach → błąd paczki nazywający oba katalogi:
    w tabeli druga sekcja nadpisałaby pierwszą."""
    _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))
    _write_document(tmp_path, "uzytkownik", ("wstep",))

    package = load_doc_package(tmp_path)

    assert not package.ok
    assert package.errors == [
        "section_id wstep jest w kilku dokumentach: administrator, uzytkownik"
    ]
    # Każdy katalog z osobna jest poprawny — tego błędu jeden katalog nie widzi.
    assert all(directory.ok for directory in package.directories)


# --- ostrzeżenia --------------------------------------------------------------------------

def test_a_long_section_is_a_warning_not_an_error(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sekcja dłuższa niż próg → ostrzeżenie z jej długością, a paczka zostaje poprawna."""
    monkeypatch.setattr(loader_doc_package, "SECTION_WARN_CHARS", 10)
    _write_document(tmp_path, "administrator")

    package = load_doc_package(tmp_path)

    assert package.ok
    assert len(package.warnings) == 1
    assert "sekcja wstep ma 20 znaków (próg 10)" in package.warnings[0]


# --- paczka syntetyczna z repo ------------------------------------------------------------

def test_the_synthetic_package_is_valid() -> None:
    """Paczka z `data/safe/instruction` → dwa zmyślone dokumenty bez błędów i sekcje
    w kolejności, której oczekuje zestaw zapytań."""
    golden  = json.loads(SYNTHETIC_GOLDEN.read_text(encoding="utf-8"))
    package = load_doc_package(SYNTHETIC_PACKAGE)

    section_ids = [
        section.section_id
        for directory in package.directories
        for section in directory.manifest.sections
    ]

    assert package.ok
    assert section_ids == golden["list_docs"]["expected_section_ids"]
    assert all(directory.manifest.synthetic for directory in package.directories)


def test_the_synthetic_package_warns_about_its_long_section() -> None:
    """Paczka syntetyczna → jedno ostrzeżenie, o sekcji celowo dłuższej niż okno embeddera."""
    warnings = load_doc_package(SYNTHETIC_PACKAGE).warnings

    assert len(warnings) == 1
    assert "adm-wykaz-uprawnien" in warnings[0]
