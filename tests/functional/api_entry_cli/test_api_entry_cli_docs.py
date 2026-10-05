import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.core_model.doc_import_report import DocsImportReport
from app.core_model.doc_package import DocPackage
from app.core_service.importer_docs import DocsImportRefused
from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from app.engine_embedding import EmbeddingError
from app.entry_cli.cli import cli

# Komendy `helpdesk docs` przez prawdziwe drzewo CLI: kody wyjścia, pytanie o potwierdzenie i to,
# co trafia na ekran. Paczki są zmyślone, w `tmp_path`; sam import zastępuje `StubRun`.

runner = CliRunner()


def _write_document(
    root:        Path,                          # np. tmp_path
    name:        str,                           # nazwa katalogu dokumentu, np. "administrator"
    section_ids: tuple[str, ...] = ("wstep",),  # sekcje w manifeście; każda dostaje plik
    synthetic:   bool = False,                  # flaga w manifeście
) -> Path:
    """
    Description:
    Zakłada katalog jednego dokumentu: manifest z podanymi sekcjami i plik `.md` na każdą.

    Example args:
        root=Path("/tmp/x")
        name="administrator"
        section_ids=("wstep",)
        synthetic=False

    Example result:
        Path("/tmp/x/administrator") z manifest.json i wstep.md
    """
    directory = root / name
    directory.mkdir()

    payload = {
        "document":  f"Instrukcja {name}",
        "version":   "4.12",
        "synthetic": synthetic,
        "sections":  [
            {"section_id": section_id, "title": f"Tytuł {section_id}", "description": "Opis"}
            for section_id in section_ids
        ],
    }

    (directory / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    for section_id in section_ids:
        (directory / f"{section_id}.md").write_text(f"Treść sekcji {section_id}.", "utf-8")

    return directory


class StubRun:
    """
    Description:
    Zastępuje przebieg importu zapisem wywołań, żeby CLI dało się testować bez embeddera, Qdranta
    i Postgresa. Zapisuje każde wywołanie i oddaje wynik ustawiony przez test.

    Stoi w miejscu `_run`, nie serwisu: ten plik testuje kontrakt komendy, a przejście przez
    prawdziwych klientów testowałoby stack.
    """

    def __init__(self) -> None:
        """
        Description:
        Buduje stub oddający raport z jednego dokumentu.

        Example args:
            (brak)

        Example result:
            StubRun z pustym `calls`
        """
        self.calls:  list[dict]       = []
        self.report: DocsImportReport = DocsImportReport(documents=1, sections=1, fragments=1)
        self.error:  Exception | None = None

    async def __call__(
        self,
        package:   DocPackage,  # np. DocPackage(path=Path("/tmp/x"), directories=[…])
        synthetic: bool,        # np. False
    ) -> DocsImportReport:
        """
        Description:
        Zapisuje wywołanie i oddaje raport albo zgłasza ustawiony błąd.

        Example args:
            package=DocPackage(path=Path("/tmp/x"), directories=[…])
            synthetic=False

        Example result:
            DocsImportReport(documents=1, sections=1, fragments=1)

        Raises:
            Exception: błąd przypisany przez test do `error`
        """
        self.calls.append({"package": package, "synthetic": synthetic})

        if self.error is not None:
            raise self.error

        return self.report


@pytest.fixture
def stub_run(monkeypatch: pytest.MonkeyPatch) -> StubRun:
    """
    Description:
    Wstawia `StubRun` w miejsce przebiegu importu i oddaje go testowi.

    Example args:
        (brak)

    Example result:
        StubRun, którego `calls` wypełnia się przy każdej komendzie
    """
    stub = StubRun()

    monkeypatch.setattr("app.entry_cli.docs.import_._run", stub)

    return stub


# --- validate -----------------------------------------------------------------------------

def test_a_valid_package_exits_zero(tmp_path: Path) -> None:
    """Poprawna paczka → kod 0, linia o dokumencie i podsumowanie."""
    _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "OK   administrator — Instrukcja administrator 4.12, sekcji: 2" in result.output
    assert "Dokumentów: 1, sekcji: 2, błędów: 0, ostrzeżeń: 0." in result.output


def test_a_synthetic_document_is_marked(tmp_path: Path) -> None:
    """Dokument zmyślony → dopisek w jego linii: operator widzi to przed importem."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "(syntetyczny)" in result.output


def test_a_broken_package_exits_one(tmp_path: Path) -> None:
    """Sekcja bez pliku → kod 1 i błąd pod nazwą katalogu, więc komenda działa jako bramka
    przed importem."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").unlink()

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "BŁĄD administrator" in result.output
    assert "brak pliku wstep.md" in result.output


def test_a_package_level_error_exits_one(tmp_path: Path) -> None:
    """Ten sam `section_id` w dwóch dokumentach → kod 1, choć każdy katalog z osobna jest OK."""
    _write_document(tmp_path, "administrator")
    _write_document(tmp_path, "uzytkownik")

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "section_id wstep jest w kilku dokumentach" in result.output


def test_a_warning_does_not_fail_validation(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sekcja dłuższa niż próg → ostrzeżenie na ekranie i kod 0."""
    monkeypatch.setattr("app.core_service.loader_doc_package.SECTION_WARN_CHARS", 5)
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "UWAGA: sekcja wstep" in result.output


def test_validate_of_a_missing_directory_exits_two(tmp_path: Path) -> None:
    """Katalog, którego nie ma → kod 2, inny niż przy zepsutej paczce."""
    result = runner.invoke(cli, ["docs", "validate", str(tmp_path / "nie-ma")])

    assert result.exit_code == 2


# --- import: odmowa przed pytaniem --------------------------------------------------------

def test_import_of_a_broken_package_runs_nothing(tmp_path: Path, stub_run: StubRun) -> None:
    """Paczka z błędami → kod 1 bez pytania o potwierdzenie i bez importu."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").unlink()

    result = runner.invoke(cli, ["docs", "import", str(tmp_path)])

    assert result.exit_code == 1
    assert "Zastąpić" not in result.output
    assert stub_run.calls == []


def test_a_synthetic_package_is_refused_without_the_flag(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """Dokument zmyślony bez `--synthetic` → kod 1 i nic nie rusza: nie trafia do właściwego
    indeksu nawet z `--yes`."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--yes"])

    assert result.exit_code == 1
    assert "właściwego indeksu" in result.output
    assert stub_run.calls == []


def test_a_real_package_is_refused_with_the_flag(tmp_path: Path, stub_run: StubRun) -> None:
    """Dokument prawdziwy z `--synthetic` → kod 1 i nic nie rusza."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--synthetic", "--yes"])

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_import_of_an_empty_package_runs_nothing(tmp_path: Path, stub_run: StubRun) -> None:
    """Pusty katalog → kod 1 i nic nie rusza: import zastępuje indeks, więc pusta paczka
    skasowałaby działający."""
    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--yes"])

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_import_of_a_missing_directory_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Katalog, którego nie ma → kod 2."""
    result = runner.invoke(cli, ["docs", "import", str(tmp_path / "nie-ma"), "--yes"])

    assert result.exit_code == 2
    assert stub_run.calls == []


# --- import: potwierdzenie ----------------------------------------------------------------

def test_import_asks_before_replacing(tmp_path: Path, stub_run: StubRun) -> None:
    """Bez `--yes`, odpowiedź „nie" → kod 1 i nic nie rusza."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "import", str(tmp_path)], input="n\n")

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_the_question_names_the_table_and_the_collection(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """Pytanie o potwierdzenie → nazywa tabelę i kolekcję, które znikną."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "import", str(tmp_path)], input="n\n")

    assert "tabelę 'docs_text' i kolekcję 'docs'" in result.output


def test_the_synthetic_flag_points_at_the_synthetic_index(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """`--synthetic` → pytanie nazywa osobny indeks syntetyczny, a import dostaje tę flagę."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--synthetic"], input="y\n")

    assert result.exit_code == 0
    assert "tabelę 'docs_text_synthetic' i kolekcję 'docs_synthetic'" in result.output
    assert stub_run.calls[0]["synthetic"] is True


def test_import_proceeds_when_confirmed(tmp_path: Path, stub_run: StubRun) -> None:
    """Potwierdzenie przyjęte → import dostaje wczytaną paczkę, a liczby trafiają na ekran."""
    _write_document(tmp_path, "administrator")
    stub_run.report = DocsImportReport(documents=1, sections=1, fragments=3)

    result = runner.invoke(cli, ["docs", "import", str(tmp_path)], input="y\n")

    assert result.exit_code == 0
    assert stub_run.calls[0]["synthetic"] is False
    assert stub_run.calls[0]["package"].section_count == 1
    assert "dokumentów: 1, sekcji: 1, fragmentów: 3" in result.output


def test_yes_skips_the_question(tmp_path: Path, stub_run: StubRun) -> None:
    """`--yes` → bez pytania, więc komenda nadaje się do skryptu."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--yes"])

    assert result.exit_code == 0
    assert "Zastąpić" not in result.output
    assert len(stub_run.calls) == 1


# --- import: awarie -----------------------------------------------------------------------

@pytest.mark.parametrize(
    "error",
    [
        pytest.param(EmbeddingError("Embedder timed out"),      id="embedder"),
        pytest.param(DbPostgresError("nie da się połączyć"),    id="postgres"),
        pytest.param(DbQdrantError("Could not reach Qdrant"),   id="qdrant"),
    ],
)
def test_an_unreachable_service_exits_two(
    tmp_path: Path,
    stub_run: StubRun,
    error:    Exception,
) -> None:
    """Leżąca zależność → kod 2: ponowienie tej samej komendy może zadziałać, inaczej niż przy
    zepsutej paczce."""
    _write_document(tmp_path, "administrator")
    stub_run.error = error

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--yes"])

    assert result.exit_code == 2


def test_a_refusal_from_the_import_itself_exits_one(tmp_path: Path, stub_run: StubRun) -> None:
    """Odmowa zgłoszona dopiero przez import → kod 1, jak przy odmowie przed pytaniem."""
    _write_document(tmp_path, "administrator")
    stub_run.error = DocsImportRefused("paczka ma błędy")

    result = runner.invoke(cli, ["docs", "import", str(tmp_path), "--yes"])

    assert result.exit_code == 1
