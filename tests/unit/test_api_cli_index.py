import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli.cli import cli
from app.model.filter_quality_report import QualityReport
from app.model.filter_quality_verdict import QualityVerdict, RuleHit
from app.model.rag_index_report import IndexBuildReport
from app.retrieval import RetrievalError

runner = CliRunner()

VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka kończy się błędem komunikacji",
    "symptoms":                      "Komunikat o braku połączenia po kliknięciu Wyślij",
    "error_codes":                   [],
    "cause":                         "Certyfikat bez uprawnienia",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}


def _corpus(directory: Path) -> Path:
    """
    Description:
    Writes one valid artifact so the command has something to read.

    Example args:
        directory=Path("/tmp/x")

    Example result:
        The same directory, now holding 33644.json
    """
    (directory / "33644.json").write_text(
        json.dumps(VALID_TICKET, ensure_ascii=False), encoding="utf-8"
    )

    return directory


def _report(indexed: int = 1, dropped_ids: tuple[str, ...] = ()) -> IndexBuildReport:
    """
    Description:
    Builds the report a stubbed run returns, with the given tickets marked as dropped.

    Example args:
        indexed=1
        dropped_ids=("19596",)

    Example result:
        IndexBuildReport(read=2, indexed=1, filtered=QualityReport(…))
    """
    verdicts = [
        QualityVerdict(
            ticket_id = ticket_id,
            hits      = [RuleHit(rule="no_resolution", evidence="Brak rozstrzygnięcia w wątku.")],
        )
        for ticket_id in dropped_ids
    ]

    return IndexBuildReport(
        read     = indexed + len(dropped_ids),
        indexed  = indexed,
        filtered = QualityReport(verdicts=verdicts),
    )


class StubRun:
    """
    Description:
    Replaces the indexing pass with a recorder, so the CLI is tested without an embedder or a
    Qdrant. Records every invocation and returns whatever outcome the test set on it.

    Stands in for `_run` rather than for the service: this file tests the CLI contract — exit
    codes, the confirmation, what gets printed — and going through the real clients would test the
    stack instead.
    """

    def __init__(self) -> None:
        """
        Description:
        Builds the stub with the default happy-path outcome.

        Example args:
            (none)

        Example result:
            StubRun returning a one-record report, recording into `calls`
        """
        self.calls:  list[dict]             = []
        self.report: IndexBuildReport       = _report()
        self.error:  Exception | None       = None

    async def __call__(self, directory: Path, drop_first: bool) -> IndexBuildReport:
        """
        Description:
        Records the call and either raises the configured error or returns the report.

        Example args:
            directory=Path("/tmp/x")
            drop_first=False

        Example result:
            IndexBuildReport(read=1, indexed=1, …)

        Raises:
            Exception: whatever the test assigned to `error`
        """
        self.calls.append({"directory": directory, "drop_first": drop_first})

        if self.error is not None:
            raise self.error

        return self.report


@pytest.fixture
def stub_run(monkeypatch: pytest.MonkeyPatch) -> StubRun:
    """
    Description:
    Installs `StubRun` in place of the CLI's indexing pass and hands it to the test.

    Example args:
        (none)

    Example result:
        StubRun whose `calls` fill up as commands run
    """
    stub = StubRun()

    monkeypatch.setattr("app.cli.index._run", stub)

    return stub


# --- build --------------------------------------------------------------------------------

def test_build_reports_counts(tmp_path: Path, stub_run: StubRun) -> None:
    """Successful build → exit 0 and a line stating what was read, indexed and dropped."""
    result = runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert result.exit_code == 0
    assert "Wczytano" in result.stdout
    assert "zaindeksowano" in result.stdout


def test_build_does_not_drop_the_collection(tmp_path: Path, stub_run: StubRun) -> None:
    """`build` → the run is asked NOT to delete first; that is the whole difference from
    `rebuild`."""
    runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert stub_run.calls[0]["drop_first"] is False


def test_build_lists_reasons_for_drops(tmp_path: Path, stub_run: StubRun) -> None:
    """Dropped records → the report names the rule and the tickets. A filter that silently halves
    the index looks exactly like one that works, and this output is where the difference shows."""
    stub_run.report = _report(indexed=1, dropped_ids=("19596",))

    result = runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert "no_resolution" in result.stdout
    assert "19596" in result.stdout


def test_empty_index_is_a_failure(tmp_path: Path, stub_run: StubRun) -> None:
    """Nothing indexed → exit 1. An empty index is never a success: a zero code would let a
    scheduled rebuild destroy a working index unnoticed."""
    stub_run.report = _report(indexed=0)

    result = runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert result.exit_code == 1


def test_missing_directory_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Directory that does not exist → exit 2, apart from "the run produced nothing" (exit 1)."""
    stub_run.error = NotADirectoryError("nie jest katalogiem: /nie-ma")

    result = runner.invoke(cli, ["index", "build", str(tmp_path / "nie-ma")])

    assert result.exit_code == 2


def test_unreachable_service_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Qdrant down → exit 2, because retrying the same command may well work — unlike an empty
    corpus, which will not fix itself."""
    stub_run.error = RetrievalError("Could not reach Qdrant")

    result = runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert result.exit_code == 2


def test_warnings_are_printed(tmp_path: Path, stub_run: StubRun) -> None:
    """Run carrying a warning → it reaches the operator. The drop-rate check is worthless if the
    output swallows it."""
    report = _report()
    report.warnings = ["filtr odrzucił 2.0% korpusu, oczekiwane ~19%"]
    stub_run.report = report

    result = runner.invoke(cli, ["index", "build", str(_corpus(tmp_path))])

    assert "UWAGA" in result.stdout


# --- rebuild ------------------------------------------------------------------------------

def test_rebuild_asks_before_destroying(tmp_path: Path, stub_run: StubRun) -> None:
    """`rebuild` without --yes, answered "no" → exit 1 and nothing runs."""
    result = runner.invoke(cli, ["index", "rebuild", str(_corpus(tmp_path))], input="n\n")

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_rebuild_names_the_collection_in_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """Confirmation prompt names the collection → confirming a destructive action without saying
    WHAT it destroys is how the wrong index gets wiped."""
    result = runner.invoke(cli, ["index", "rebuild", str(_corpus(tmp_path))], input="n\n")

    assert "tickets" in result.stdout


def test_rebuild_proceeds_when_confirmed(tmp_path: Path, stub_run: StubRun) -> None:
    """Confirmation accepted → the run is asked to delete first."""
    result = runner.invoke(cli, ["index", "rebuild", str(_corpus(tmp_path))], input="y\n")

    assert result.exit_code == 0
    assert stub_run.calls[0]["drop_first"] is True


def test_rebuild_with_yes_skips_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """`--yes` → no question asked, so the command is usable from a script."""
    result = runner.invoke(cli, ["index", "rebuild", str(_corpus(tmp_path)), "--yes"])

    assert result.exit_code == 0
    assert stub_run.calls[0]["drop_first"] is True
