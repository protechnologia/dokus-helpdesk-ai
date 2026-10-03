import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli.cli import cli

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
    """Directory of valid artifacts → exit code 0 and a summary line."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "Sprawdzono 1, błędnych 0." in result.output


def test_broken_artifact_exits_one(tmp_path: Path) -> None:
    """Directory with an invalid artifact → exit code 1, so the command works as a pipeline gate."""
    _write(tmp_path, "bad.json", {**VALID_TICKET, "resolution": "nieznane"})

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "BŁĄD bad.json" in result.output


def test_missing_directory_exits_two(tmp_path: Path) -> None:
    """Non-existent directory → exit code 2, distinct from broken artifacts (1)."""
    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path / "nie-ma")])

    # A pipeline must be able to tell "you pointed me at nothing" from "the corpus is broken".
    assert result.exit_code == 2


def test_valid_files_are_quiet_by_default(tmp_path: Path) -> None:
    """Passing files → not listed, so a corpus run shows problems instead of scrolling them off."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert "ok.json" not in result.output


def test_verbose_lists_valid_files(tmp_path: Path) -> None:
    """--verbose → passing files listed too, for checking a small directory by eye."""
    _write(tmp_path, "ok.json", VALID_TICKET)

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path), "--verbose"])

    assert "OK   ok.json" in result.output


def test_error_detail_is_printed(tmp_path: Path) -> None:
    """Invalid artifact → the reason is printed, not only the file name."""
    _write(tmp_path, "bad.json", {**VALID_TICKET, "resolution": "nieznane"})

    result = runner.invoke(cli, ["tickets", "validate", str(tmp_path)])

    assert "naprawione" in result.output   # the allowed values, quoted back to the operator


def test_command_is_registered_under_tickets() -> None:
    """`helpdesk tickets --help` → lists validate, so the subcommand tree is actually wired."""
    result = runner.invoke(cli, ["tickets", "--help"])

    assert result.exit_code == 0
    assert "validate" in result.output
