import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.core_model.tickets.quality_report import QualityReport
from app.core_model.tickets.quality_verdict import QualityVerdict, RuleHit
from app.core_model.tickets.tickets_index_report import TicketsIndexReport
from app.db_qdrant import DbQdrantError
from app.entry_cli.cli import cli

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


def _report(indexed: int = 1, dropped_ids: tuple[str, ...] = ()) -> TicketsIndexReport:
    """
    Description:
    Builds the report a stubbed run returns, with the given tickets marked as dropped.

    Example args:
        indexed=1
        dropped_ids=("19596",)

    Example result:
        TicketsIndexReport(read=2, indexed=1, filtered=QualityReport(…))
    """
    verdicts = [
        QualityVerdict(
            ticket_id = ticket_id,
            hits      = [RuleHit(rule="no_resolution", evidence="Brak rozstrzygnięcia w wątku.")],
        )
        for ticket_id in dropped_ids
    ]

    return TicketsIndexReport(
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
        self.report: TicketsIndexReport       = _report()
        self.error:  Exception | None       = None

    async def __call__(self, directory: Path, drop_first: bool) -> TicketsIndexReport:
        """
        Description:
        Records the call and either raises the configured error or returns the report.

        Example args:
            directory=Path("/tmp/x")
            drop_first=False

        Example result:
            TicketsIndexReport(read=1, indexed=1, …)

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

    monkeypatch.setattr("app.entry_cli.tickets.common._run", stub)

    return stub


# --- build --------------------------------------------------------------------------------

def test_build_reports_counts(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy udane `helpdesk tickets index` kończy się kodem 0 i wypisuje podsumowanie
    z liczbą zgłoszeń wczytanych i zaindeksowanych.

    Wyłapuje komendę, która kończy się błędem mimo udanego przebiegu albo nie pokazuje
    podsumowania — operator nie wiedziałby wtedy, ile zgłoszeń trafiło do indeksu."""
    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert result.exit_code == 0
    assert "Wczytano" in result.stdout
    assert "zaindeksowano" in result.stdout


def test_build_does_not_drop_the_collection(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets index` uruchamia indeksację bez kasowania kolekcji.

    Wyłapuje pomylenie tej komendy z `helpdesk tickets reindex`, od której różni ją tylko to:
    zwykłe dołożenie zgłoszeń kasowałoby wtedy cały indeks, i to bez pytania."""
    runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert stub_run.calls[0]["drop_first"] is False


def test_build_lists_reasons_for_drops(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy przy odrzuconym zgłoszeniu `helpdesk tickets index` wypisuje nazwę reguły,
    która je odrzuciła (`no_resolution`), i numer tego zgłoszenia (19596).

    Wyłapuje raport, który przemilcza odrzucenia: filtr, który po cichu wyrzuca połowę zgłoszeń,
    wygląda dokładnie jak działający, a różnicę widać tylko w tym wypisie."""
    stub_run.report = _report(indexed=1, dropped_ids=("19596",))

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert "no_resolution" in result.stdout
    assert "19596" in result.stdout


def test_empty_index_is_a_failure(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets index` kończy się kodem 1, gdy przebieg nie zaindeksował
    żadnego zgłoszenia.

    Wyłapuje pusty indeks zgłoszony jako sukces: przy kodzie 0 zaplanowana przebudowa mogłaby
    zniszczyć działający indeks i nikt by tego nie zauważył."""
    stub_run.report = _report(indexed=0)

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert result.exit_code == 1


def test_missing_directory_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets index` kończy się kodem 2, gdy indeksacja zgłasza, że
    wskazanego katalogu nie ma (`NotADirectoryError`).

    Wyłapuje pomylenie złej ścieżki z przebiegiem, który nic nie zaindeksował (kod 1): potok nie
    odróżniłby wtedy błędu w konfiguracji od rzeczywiście pustego wyniku."""
    stub_run.error = NotADirectoryError("nie jest katalogiem: /nie-ma")

    result = runner.invoke(cli, ["tickets", "index", str(tmp_path / "nie-ma")])

    assert result.exit_code == 2


def test_unreachable_service_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets index` kończy się kodem 2, gdy indeksacja zgłasza, że
    Qdrant nie odpowiada (`DbQdrantError`).

    Wyłapuje awarię usługi pomyloną z pustym korpusem (kod 1) albo wypuszczoną jako nieobsłużony
    wyjątek: przy leżącej usłudze ponowienie tej samej komendy może zadziałać, a pusty korpus sam
    się nie naprawi."""
    stub_run.error = DbQdrantError("Could not reach Qdrant")

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert result.exit_code == 2


def test_warnings_are_printed(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy ostrzeżenie z raportu indeksacji (tu: filtr odrzucił 2% korpusu zamiast
    oczekiwanych około 19%) trafia na ekran w linii „UWAGA".

    Wyłapuje komendę, która gubi ostrzeżenia: kontrola odsetka odrzuconych zgłoszeń nic nie daje,
    jeśli operator nie zobaczy jej wyniku."""
    report = _report()
    report.warnings = ["filtr odrzucił 2.0% korpusu, oczekiwane ~19%"]
    stub_run.report = report

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert "UWAGA" in result.stdout


# --- rebuild ------------------------------------------------------------------------------

def test_rebuild_asks_before_destroying(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets reindex` bez `--yes` pyta o potwierdzenie, a po odpowiedzi
    „nie" kończy się kodem 1 i nie uruchamia indeksacji.

    Wyłapuje komendę, która kasuje kolekcję bez pytania albo mimo odmowy: uruchomiona przez
    pomyłkę na pustym albo złym katalogu nie zostawiłaby nic do przeszukania."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path))], input="n\n")

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_rebuild_names_the_collection_in_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy pytanie o potwierdzenie w `helpdesk tickets reindex` zawiera nazwę kolekcji,
    która ma zostać skasowana (`tickets`).

    Wyłapuje pytanie, które nie mówi, co zniknie: potwierdzając w ciemno, łatwo skasować nie ten
    indeks, o który chodziło."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path))], input="n\n")

    assert "tickets" in result.stdout


def test_rebuild_proceeds_when_confirmed(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy po odpowiedzi „tak" `helpdesk tickets reindex` kończy się kodem 0 i uruchamia
    indeksację z kasowaniem kolekcji.

    Wyłapuje przebudowę, która po potwierdzeniu nie rusza albo nie kasuje starej kolekcji:
    zamiast indeksu zbudowanego od zera zostałyby w nim stare punkty."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path))], input="y\n")

    assert result.exit_code == 0
    assert stub_run.calls[0]["drop_first"] is True


def test_rebuild_with_yes_skips_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets reindex --yes` kończy się kodem 0 i uruchamia indeksację
    z kasowaniem kolekcji, nie czekając na odpowiedź operatora.

    Wyłapuje komendę, która mimo `--yes` czeka na potwierdzenie: nie dałoby się jej uruchomić ze
    skryptu, bo nikt by na pytanie nie odpowiedział."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path)), "--yes"])

    assert result.exit_code == 0
    assert stub_run.calls[0]["drop_first"] is True
