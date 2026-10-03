import json
from pathlib import Path

import pytest

from app.service.validator_ticket_parsed import validate_directory, validate_file

VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka kończy się błędem komunikacji",
    "symptoms":                      "Komunikat o braku połączenia po kliknięciu Wyślij",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "brak",
    "solution":                      "brak",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}


def _write(directory: Path, name: str, payload: dict | str) -> Path:
    """
    Description:
    Writes an artifact file, accepting either a dict to serialise or raw text — raw text is how a
    malformed file is produced, which no dict could express.

    Example args:
        directory=Path("/tmp/x")
        name="33644.json"
        payload={"ticket_id": "33644", …}

    Example result:
        Path("/tmp/x/33644.json")
    """
    path = directory / name
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")

    return path


def test_valid_file_passes(tmp_path: Path) -> None:
    """Artifact matching the contract → verdict with no errors."""
    verdict = validate_file(_write(tmp_path, "ok.json", VALID_TICKET))

    assert verdict.ok
    assert verdict.errors == []


def test_unknown_field_is_reported(tmp_path: Path) -> None:
    """Key outside the schema → reported, never dropped (the LLM run producing it is one-off)."""
    verdict = validate_file(_write(tmp_path, "extra.json", {**VALID_TICKET, "severity": "wysoka"}))

    assert not verdict.ok
    assert any("severity" in error for error in verdict.errors)


def test_resolution_outside_vocabulary_is_reported(tmp_path: Path) -> None:
    """Outcome kind absent from the vocabulary → error naming the allowed values."""
    broken = {**VALID_TICKET, "resolution": "zamkniete-bo-tak"}

    verdict = validate_file(_write(tmp_path, "res.json", broken))

    assert not verdict.ok
    # The message must list what IS allowed; "invalid value" alone leaves the operator guessing.
    assert any("naprawione" in error for error in verdict.errors)


def test_foreign_vocabulary_version_is_reported(tmp_path: Path) -> None:
    """Record from another vocabulary version → error quoting that version."""
    broken = {**VALID_TICKET, "resolution_vocabulary_version": 99}

    verdict = validate_file(_write(tmp_path, "ver.json", broken))

    assert not verdict.ok
    assert any("99" in error for error in verdict.errors)


def test_malformed_json_is_reported_not_raised(tmp_path: Path) -> None:
    """Unreadable file → verdict with an error, so one bad file cannot abort a corpus run."""
    verdict = validate_file(_write(tmp_path, "broken.json", '{ "ticket_id": '))

    assert not verdict.ok
    assert verdict.errors


def test_every_error_line_names_a_location(tmp_path: Path) -> None:
    """Error line → prefixed with the field (or `rekord`), because a raw dump is unactionable."""
    verdict = validate_file(_write(tmp_path, "extra.json", {**VALID_TICKET, "severity": "x"}))

    assert all(":" in error for error in verdict.errors)


def test_directory_report_separates_valid_from_broken(tmp_path: Path) -> None:
    """Mixed directory → every file gets a verdict, and `failed` lists only the broken ones."""
    _write(tmp_path, "a_ok.json", VALID_TICKET)
    _write(tmp_path, "b_bad.json", {**VALID_TICKET, "resolution": "nieznane"})
    _write(tmp_path, "c_ok.json", {**VALID_TICKET, "ticket_id": "999"})

    report = validate_directory(tmp_path)

    assert len(report.verdicts) == 3
    assert not report.ok
    assert [verdict.path.name for verdict in report.failed] == ["b_bad.json"]


def test_files_are_reported_in_stable_order(tmp_path: Path) -> None:
    """Directory → verdicts sorted by name, so two runs over one corpus stay comparable."""
    for name in ("c.json", "a.json", "b.json"):
        _write(tmp_path, name, VALID_TICKET)

    names = [verdict.path.name for verdict in validate_directory(tmp_path).verdicts]

    assert names == ["a.json", "b.json", "c.json"]


def test_empty_directory_passes(tmp_path: Path) -> None:
    """Directory with no artifacts → empty, passing report (it is empty until stage 10)."""
    report = validate_directory(tmp_path)

    assert report.ok
    assert report.verdicts == []


def test_non_json_files_are_ignored(tmp_path: Path) -> None:
    """Directory holding other files → only *.json is checked, notes and READMEs are not."""
    _write(tmp_path, "ok.json", VALID_TICKET)
    (tmp_path / "notatki.md").write_text("nie artefakt", encoding="utf-8")

    assert len(validate_directory(tmp_path).verdicts) == 1


def test_missing_directory_raises(tmp_path: Path) -> None:
    """Path that is not a directory → NotADirectoryError, distinct from broken artifacts."""
    with pytest.raises(NotADirectoryError):
        validate_directory(tmp_path / "nie-ma")
