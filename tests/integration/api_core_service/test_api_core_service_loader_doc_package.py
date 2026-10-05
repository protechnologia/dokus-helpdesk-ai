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
    """Sprawdza, czy poprawna paczka z jednym dokumentem i dwiema sekcjami zostaje wczytana
    w całości: paczka jest uznana za poprawną, ma dwie sekcje, a czytnik oddaje tytuł dokumentu
    z manifestu i treść obu plików.

    Wyłapuje czytnik, który gubi treść sekcji albo zgłasza błędy w poprawnej paczce — takiej
    dokumentacji nie dałoby się zaindeksować."""
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
    """Sprawdza, czy dokumenty wracają w kolejności nazw katalogów: katalog `uzytkownik` powstaje
    tu pierwszy, a mimo to w wyniku stoi po katalogu `administrator`.

    Wyłapuje kolejność zależną od systemu plików: dwa przebiegi po tej samej paczce dawałyby
    wtedy różne raporty i nie dałoby się ich porównać."""
    _write_document(tmp_path, "uzytkownik", ("b",))
    _write_document(tmp_path, "administrator", ("a",))

    package = load_doc_package(tmp_path)

    assert [directory.path.name for directory in package.directories] == [
        "administrator",
        "uzytkownik",
    ]


def test_the_body_is_kept_verbatim(tmp_path: Path) -> None:
    """Sprawdza, czy treść sekcji wraca znak w znak, razem z wcięciem oraz pustymi liniami na
    początku i na końcu pliku.

    Wyłapuje czytnik, który przycina albo porządkuje tekst: treść w tej postaci idzie do bazy
    i do agenta, więc po takiej zmianie różniłaby się od pliku z dokumentacją."""
    directory = _write_document(tmp_path, "administrator")
    body      = "\n  Uprawnienie nadaje administrator.\n\n- pozycja\n\n"

    (directory / "wstep.md").write_text(body, encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].bodies["wstep"] == body


def test_an_empty_root_is_a_valid_empty_package(tmp_path: Path) -> None:
    """Sprawdza, czy pusty katalog daje pustą, poprawną paczkę: bez dokumentów i bez błędów.

    Wyłapuje czytnik, który pusty katalog uznaje za błąd: katalog właściwej dokumentacji jest
    pusty, dopóki jej nie przygotowano, więc sprawdzenie paczki zgłaszałoby wtedy błąd, choć nic
    nie jest zepsute."""
    package = load_doc_package(tmp_path)

    assert package.ok
    assert package.directories == []


def test_hidden_directories_and_loose_files_are_not_documents(tmp_path: Path) -> None:
    """Sprawdza, czy katalog ukryty (`.git`) i plik leżący luzem (`README.md`) obok dokumentu są
    pomijane: paczka jest poprawna i ma jeden dokument.

    Wyłapuje czytnik, który każdy podkatalog bierze za dokument: katalog `.git` dostałby wtedy
    błąd braku manifestu i poprawna paczka nie przeszłaby sprawdzenia."""
    _write_document(tmp_path, "administrator")
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Notatka o paczce.", encoding="utf-8")

    package = load_doc_package(tmp_path)

    assert package.ok
    assert [directory.path.name for directory in package.directories] == ["administrator"]


# --- zły katalog --------------------------------------------------------------------------

def test_a_missing_root_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka, pod którą nie ma katalogu, kończy się wyjątkiem
    `NotADirectoryError`, a nie pustą paczką.

    Wyłapuje sytuację, w której literówka w ścieżce wygląda jak poprawna paczka bez dokumentów
    i nikt nie zauważa, że nic nie zostało wczytane."""
    with pytest.raises(NotADirectoryError):
        load_doc_package(tmp_path / "nie-ma")


def test_a_document_directory_given_as_the_package_is_refused(tmp_path: Path) -> None:
    """Sprawdza, czy wskazanie katalogu jednego dokumentu zamiast katalogu całej paczki daje
    błąd, który mówi, żeby podać katalog nadrzędny.

    Wyłapuje łatwą pomyłkę w ścieżce: katalog dokumentu nie ma podkatalogów, więc bez tego błędu
    wyglądałby jak poprawna, pusta paczka."""
    directory = _write_document(tmp_path, "administrator")

    package = load_doc_package(directory)

    assert not package.ok
    assert "katalog nadrzędny" in package.errors[0]


# --- manifest -----------------------------------------------------------------------------

def test_a_directory_without_a_manifest_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy podkatalog bez pliku `manifest.json` trafia do wyniku z błędem, który mówi,
    że tego pliku brakuje, zamiast zostać pominięty.

    Wyłapuje ciche pominięcie takiego katalogu: cały dokument nie trafiłby do indeksu i nic by
    tego nie zgłosiło."""
    (tmp_path / "administrator").mkdir()

    directory = load_doc_package(tmp_path).directories[0]

    assert directory.manifest is None
    assert directory.errors   == ["brak pliku manifest.json"]


def test_a_manifest_that_is_not_json_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy manifest z zepsutym JSON-em daje jeden błąd katalogu, który zaczyna się od
    nazwy pliku `manifest.json`.

    Wyłapuje dwie usterki: wyjątek, który przez jeden zepsuty plik przerwałby czytanie całej
    paczki, oraz błąd, z którego nie widać, który plik trzeba poprawić."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "manifest.json").write_text("{nie json", encoding="utf-8")

    errors = load_doc_package(tmp_path).directories[0].errors

    assert len(errors) == 1
    assert errors[0].startswith("manifest.json: ")


def test_a_manifest_outside_the_contract_names_the_field(tmp_path: Path) -> None:
    """Sprawdza, czy manifest z pustym wydaniem (`version`) i z kluczem, którego kontrakt nie
    przewiduje (`author`), dostaje błąd z nazwą każdego z tych dwóch pól.

    Wyłapuje manifest przyjęty mimo braku wydania albo z nadmiarowym kluczem, a także raport,
    który zgłasza tylko pierwszy problem albo nie mówi, którego pola dotyczy."""
    _write_document(tmp_path, "administrator", version="", author="Jan Kowalski")

    errors = load_doc_package(tmp_path).directories[0].errors

    assert any("version" in error for error in errors)
    assert any("author" in error for error in errors)


# --- zgodność manifestu z katalogiem ------------------------------------------------------

def test_a_section_without_its_file_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy sekcja wpisana do manifestu, ale bez swojego pliku `.md`, daje błąd z nazwą
    brakującego pliku, a treść drugiej sekcji tego dokumentu jest mimo to wczytana.

    Wyłapuje czytnik, który nie zauważa brakującego pliku: sekcja z manifestu nie miałaby wtedy
    treści i nikt by się o tym nie dowiedział przed indeksacją."""
    directory = _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))
    (directory / "uprawnienia.md").unlink()

    loaded = load_doc_package(tmp_path).directories[0]

    assert loaded.errors == ["brak pliku uprawnienia.md"]
    assert set(loaded.bodies) == {"wstep"}


def test_a_file_without_a_manifest_entry_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy plik `.md`, którego nie ma w manifeście, daje błąd z nazwą tego pliku.

    Wyłapuje sprawdzanie zgodności tylko w jedną stronę, od manifestu do plików: sekcja dodana
    jako sam plik nie trafiłaby do indeksu i nic by tego nie zgłosiło."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "nowa-sekcja.md").write_text("Treść bez wpisu.", encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].errors == [
        "plik bez wpisu w manifeście: nowa-sekcja.md"
    ]


@pytest.mark.parametrize("content", ["", "  \n\n"])
def test_an_empty_section_file_is_reported(tmp_path: Path, content: str) -> None:
    """Sprawdza, czy plik sekcji bez treści daje błąd, że jest pusty. Dotyczy to pliku zupełnie
    pustego i pliku, w którym są same spacje i puste linie.

    Wyłapuje pustą sekcję przyjętą jako poprawna: sekcja bez tekstu niczego nie opisuje,
    a w indeksie wyglądałaby jak każda inna."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").write_text(content, encoding="utf-8")

    assert load_doc_package(tmp_path).directories[0].errors == ["wstep.md jest pusty"]


def test_a_section_file_that_is_not_utf8_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy plik sekcji zapisany w innym kodowaniu niż UTF-8 (tu cp1250) daje jeden błąd
    z nazwą tego pliku, a nie wyjątek.

    Wyłapuje wyjątek, który przez jeden źle zapisany plik przerwałby czytanie całej paczki, zanim
    widać jej pozostałe problemy."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").write_bytes("Treść sekcji".encode("cp1250"))

    errors = load_doc_package(tmp_path).directories[0].errors

    assert len(errors) == 1
    assert errors[0].startswith("wstep.md nie jest tekstem UTF-8")


def test_every_problem_of_a_directory_is_reported_at_once(tmp_path: Path) -> None:
    """Sprawdza, czy trzy różne wady jednego dokumentu — brak pliku sekcji, pusty plik sekcji
    i plik bez wpisu w manifeście — wracają razem, jako trzy błędy z jednego przebiegu.

    Wyłapuje czytnik, który zatrzymuje się na pierwszym błędzie: paczkę trzeba by wtedy poprawiać
    i sprawdzać od nowa po jednej wadzie naraz."""
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
    """Sprawdza, czy przy dwóch dokumentach, z których jeden nie ma manifestu, paczka jest uznana
    za niepoprawną, ale dobry dokument jest wczytany i oceniony jako poprawny.

    Wyłapuje dwie usterki: zepsuty dokument, który psuje ocenę pozostałych, oraz paczkę uznaną za
    poprawną, choć jeden z jej dokumentów ma błąd."""
    _write_document(tmp_path, "administrator")
    (tmp_path / "uzytkownik").mkdir()

    package = load_doc_package(tmp_path)

    assert not package.ok
    assert [directory.ok for directory in package.directories] == [True, False]


# --- ponad dokumentami --------------------------------------------------------------------

def test_the_same_section_id_in_two_documents_is_a_package_error(tmp_path: Path) -> None:
    """Sprawdza, czy ten sam identyfikator sekcji (`wstep`) użyty w dwóch dokumentach daje błąd
    całej paczki, który nazywa oba katalogi, choć każdy dokument z osobna jest poprawny.

    Wyłapuje brak sprawdzenia ponad dokumentami: identyfikator sekcji jest kluczem w tabeli, więc
    druga sekcja nadpisałaby pierwszą bez żadnego śladu."""
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
    """Sprawdza, czy sekcja dłuższa niż próg dostaje ostrzeżenie, a nie błąd: przy progu
    obniżonym do 10 znaków sekcja o 20 znakach daje jedno ostrzeżenie z obiema liczbami, a paczka
    zostaje poprawna.

    Wyłapuje długą sekcję potraktowaną jak błąd, co wstrzymałoby indeksację całej paczki, oraz
    ostrzeżenie, które znika albo nie podaje długości sekcji."""
    monkeypatch.setattr(loader_doc_package, "SECTION_WARN_CHARS", 10)
    _write_document(tmp_path, "administrator")

    package = load_doc_package(tmp_path)

    assert package.ok
    assert len(package.warnings) == 1
    assert "sekcja wstep ma 20 znaków (próg 10)" in package.warnings[0]


# --- paczka syntetyczna z repo ------------------------------------------------------------

def test_the_synthetic_package_is_valid() -> None:
    """Sprawdza, czy paczka syntetyczna z `data/safe/instruction` jest poprawna: nie ma błędów,
    każdy jej dokument jest oznaczony jako zmyślony, a sekcje stoją w tej samej kolejności, którą
    zapisano w zestawie zapytań `docs-synthetic.json`.

    Wyłapuje zmianę w paczce, po której przestaje ona pasować do zestawu zapytań albo traci
    oznaczenie danych zmyślonych: na paczce i zestawie razem stoją pomiary narzędzi dokumentacji,
    a dokument bez oznaczenia mógłby trafić do właściwego indeksu."""
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
    """Sprawdza, czy paczka syntetyczna daje dokładnie jedno ostrzeżenie o długiej sekcji i czy
    dotyczy ono sekcji `adm-wykaz-uprawnien`, celowo dłuższej, niż embedder przyjmuje naraz.

    Wyłapuje zmianę paczki, po której ta sekcja przestaje przekraczać próg albo przekracza go
    też inna — czyli paczkę, która nie ma już swojego jednego, zamierzonego przypadku długiej
    sekcji."""
    warnings = load_doc_package(SYNTHETIC_PACKAGE).warnings

    assert len(warnings) == 1
    assert "adm-wykaz-uprawnien" in warnings[0]
