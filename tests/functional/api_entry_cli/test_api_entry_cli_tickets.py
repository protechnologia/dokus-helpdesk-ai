import json
from pathlib import Path

from typer.testing import CliRunner

from app.entry_cli.cli import cli

runner = CliRunner()

VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka kończy się błędem komunikacji",
    "symptoms":                      "Komunikat o braku połączenia po kliknięciu Wyślij",
    "error_codes":                   [],
    "cause":                         "brak",
    "solution":                      "brak",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}


def _write(directory: Path, name: str, payload: dict) -> None:
    """
    Description:
    Writes one artifact file into the directory under test.

    Example args:
        directory=Path("/tmp/x")
        name="ok.json"
        payload={"ticket_id": "33644", …}

    Example result:
        None — the file exists on disk
    """
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_valid_directory_exits_zero(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk tickets validate` na katalogu z jednym poprawnym plikiem zgłoszenia
    kończy się kodem 0 i wypisuje podsumowanie: sprawdzono 1, błędnych 0.

    Wyłapuje komendę, która zgłasza błąd przy poprawnych plikach albo nie mówi, ile ich
    sprawdziła — przebieg, który niczego nie przeczytał, wyglądałby wtedy tak samo jak udany."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "Sprawdzono 1, błędnych 0." in result.output


def test_broken_artifact_exits_one(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk tickets validate` kończy się kodem 1 i wypisuje „BŁĄD" z nazwą
    pliku, gdy w katalogu jest zgłoszenie z niedozwoloną wartością pola `resolution`.

    Wyłapuje komendę, która przy błędnym pliku kończy się kodem 0: nie dałoby się jej użyć jako
    bramki w potoku, bo skrypt nie zauważyłby zepsutego zgłoszenia."""
    _write(tmp_path, "bad.json", {**VALID_TICKET, "resolution": "nieznane"})

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "BŁĄD bad.json" in result.output


def test_missing_directory_exits_two(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk tickets validate` kończy się kodem 2, gdy wskazanego katalogu nie
    ma — to inny kod niż 1 przy błędnych plikach.

    Wyłapuje pomieszanie tych dwóch sytuacji: potok nie odróżniłby wtedy złej ścieżki od
    zepsutego korpusu."""
    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path / "nie-ma")])

    # A pipeline must be able to tell "you pointed me at nothing" from "the corpus is broken".
    assert result.exit_code == 2


def test_valid_files_are_quiet_by_default(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk tickets validate` bez dodatkowych opcji nie wypisuje nazw plików,
    które są poprawne.

    Wyłapuje komendę, która wymienia każdy sprawdzony plik: przy przebiegu po całym korpusie
    błędy przewinęłyby się poza ekran między liniami o poprawnych plikach."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert "ok.json" not in result.output


def test_verbose_lists_valid_files(tmp_path: Path) -> None:
    """Sprawdza, czy z opcją `--verbose` komenda `helpdesk tickets validate` wypisuje także
    poprawne pliki, każdy w linii „OK" ze swoją nazwą.

    Wyłapuje opcję, która przestała działać: przy małym katalogu nie dałoby się sprawdzić na
    oko, które pliki komenda faktycznie przeczytała."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path), "--verbose"])

    assert "OK   ok.json" in result.output


def test_error_detail_is_printed(tmp_path: Path) -> None:
    """Sprawdza, czy przy zgłoszeniu z niedozwoloną wartością pola `resolution` komenda
    `helpdesk tickets validate` wypisuje powód błędu razem z wartościami dozwolonymi (jest wśród
    nich „naprawione").

    Wyłapuje raport, który podaje samą nazwę błędnego pliku: operator wiedziałby, że plik jest
    zły, ale nie wiedziałby, co w nim poprawić."""
    _write(tmp_path, "bad.json", {**VALID_TICKET, "resolution": "nieznane"})

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert "naprawione" in result.output   # the allowed values, quoted back to the operator


def test_command_is_registered_under_tickets() -> None:
    """Sprawdza, czy `helpdesk tickets --help` kończy się kodem 0 i wymienia komendę `validate`.

    Wyłapuje komendę, której nie podpięto do drzewa `helpdesk tickets`: jej kod byłby w repo, ale
    nie dałoby się jej uruchomić z konsoli."""
    result = runner.invoke(cli, ["tickets", "--help"])

    assert result.exit_code == 0
    assert "validate" in result.output
