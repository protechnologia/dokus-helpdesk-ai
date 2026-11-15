import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.core_model.tickets.quality_report import QualityReport
from app.core_model.tickets.quality_verdict import QualityVerdict, RuleHit
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_index_report import TicketsIndexReport
from app.db_postgres import DbPostgresError
from app.db_postgres.table.tickets.table import TICKETS_TABLE
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
    "excluded_causes":               [],
    "useful":                        True,
    "useful_reason":                 "Wątek podaje przyczynę i rozwiązanie.",
}


def _corpus(directory: Path) -> Path:
    """
    Description:
    Zapisuje jedną poprawną kartę w `cards/` korpusu, żeby komenda miała co czytać.

    Example args:
        directory=Path("/tmp/x")

    Example result:
        Ten sam katalog, z kartą w cards/33644.json
    """
    cards = directory / "cards"
    cards.mkdir(exist_ok=True)

    (cards / "33644.json").write_text(
        json.dumps(VALID_TICKET, ensure_ascii=False), encoding="utf-8"
    )

    return directory


def _report(
    indexed:     int             = 1,      # np. 1
    dropped_ids: tuple[str, ...] = (),     # np. ("19596",)
    threads:     int | None      = None,   # np. 1; None — korpus bez anonymized/
) -> TicketsIndexReport:
    """
    Description:
    Builds the report a stubbed run returns, with the given tickets marked as dropped.

    Example args:
        indexed=1
        dropped_ids=("19596",)
        threads=1

    Example result:
        TicketsIndexReport(read=2, indexed=1, threads=1, filtered=QualityReport(…))
    """
    verdicts = [
        QualityVerdict(
            ticket_id = ticket_id,
            hits      = [RuleHit(rule="not_useful", evidence="Wątek nie niesie wiedzy.")],
        )
        for ticket_id in dropped_ids
    ]

    return TicketsIndexReport(
        read     = indexed + len(dropped_ids),
        indexed  = indexed,
        threads  = threads,
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

    async def __call__(self, corpus: TicketsCorpus, drop_first: bool) -> TicketsIndexReport:
        """
        Description:
        Records the call and either raises the configured error or returns the report.

        Example args:
            corpus=TicketsCorpus(root=Path("/tmp/x"))
            drop_first=False

        Example result:
            TicketsIndexReport(read=1, indexed=1, …)

        Raises:
            Exception: whatever the test assigned to `error`
        """
        self.calls.append({"corpus": corpus, "drop_first": drop_first})

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
    która je odrzuciła (`not_useful`), i numer tego zgłoszenia (19596).

    Wyłapuje raport, który przemilcza odrzucenia: filtr, który po cichu wyrzuca połowę zgłoszeń,
    wygląda dokładnie jak działający, a różnicę widać tylko w tym wypisie."""
    stub_run.report = _report(indexed=1, dropped_ids=("19596",))

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert "not_useful" in result.stdout
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


def test_rebuild_names_the_directory_in_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy pytanie o potwierdzenie w `helpdesk tickets reindex` zawiera katalog, z którego
    kolekcja ma zostać zbudowana.

    Wyłapuje pytanie, które nie mówi, skąd przyjdzie nowy indeks: przy katalogu wziętym
    z konfiguracji operator nie wiedziałby, że przebudowa sięgnie gdzie indziej, niż myśli."""
    directory = _corpus(tmp_path)

    result = runner.invoke(cli, ["tickets", "reindex", str(directory)], input="n\n")

    assert str(directory) in result.stdout


@pytest.mark.parametrize("command", [["index"], ["reindex", "--yes"]])
def test_without_a_directory_the_configured_corpus_is_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stub_run: StubRun, command: list[str]
) -> None:
    """Sprawdza, czy `helpdesk tickets index` i `helpdesk tickets reindex` bez katalogu indeksują
    korpus wskazany przez `TICKETS_CORPUS_DIR`.

    Wyłapuje komendę, która bez argumentu sięga gdzie indziej niż zapis kart i wątków, np. w dawne
    `data/unsafe/parsed`: przebudowa nie miałaby z czego zbudować indeksów albo zbudowałaby je
    z innych plików niż te, które zapisuje trasa."""
    monkeypatch.setenv("TICKETS_CORPUS_DIR", str(tmp_path))

    result = runner.invoke(cli, ["tickets", *command])

    assert result.exit_code == 0
    assert stub_run.calls[0]["corpus"].root == tmp_path


@pytest.mark.parametrize("command", [["index"], ["reindex", "--yes"]])
def test_the_directory_argument_is_the_corpus(
    tmp_path: Path, stub_run: StubRun, command: list[str]
) -> None:
    """Sprawdza, czy katalog podany komendom `index` i `reindex` jest katalogiem korpusu, z którego
    indekser bierze `cards/` i `anonymized/`, a nie katalogiem samych kart.

    Wyłapuje komendę, która traktuje argument jak katalog kart: `helpdesk tickets reindex
    data/unsafe/golden` szukałby kart w `golden/` zamiast w `golden/cards/`."""
    result = runner.invoke(cli, ["tickets", *command, str(_corpus(tmp_path))])

    assert result.exit_code == 0
    assert stub_run.calls[0]["corpus"] == TicketsCorpus(root=tmp_path)


def test_unreachable_postgres_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets index` kończy się kodem 2 i wypisuje „BŁĄD”, gdy indeksacja
    zgłasza, że Postgres nie odpowiada (`DbPostgresError`) przy zapisie wątków.

    Wyłapuje awarię tabeli wątków wypuszczoną jako nieobsłużony wyjątek ze śladem stosu: operator
    nie odróżniłby leżącej bazy, którą wystarczy podnieść, od błędu w kodzie."""
    stub_run.error = DbPostgresError("Could not reach Postgres")

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert result.exit_code == 2
    assert "BŁĄD" in result.output


@pytest.mark.parametrize(
    ("threads", "expected"),
    [(3, "Wątków w tabeli: 3."), (None, "tabela wątków bez zmian")],
)
def test_the_report_says_what_happened_to_the_threads(
    tmp_path: Path, stub_run: StubRun, threads: int | None, expected: str
) -> None:
    """Sprawdza, czy podsumowanie `helpdesk tickets index` mówi, ile wątków trafiło do tabeli,
    a przy korpusie bez `anonymized/` — że tabela wątków została bez zmian.

    Wyłapuje podsumowanie, które milczy o wątkach: po indeksacji golden setu operator nie
    wiedziałby, że wyszukiwanie po słowach nadal stoi na starej tabeli albo pustej."""
    stub_run.report = _report(threads=threads)

    result = runner.invoke(cli, ["tickets", "index", str(_corpus(tmp_path))])

    assert expected in result.stdout


def test_rebuild_names_the_threads_table_when_the_corpus_has_threads(
    tmp_path: Path, stub_run: StubRun
) -> None:
    """Sprawdza, czy przy korpusie z katalogiem `anonymized/` pytanie przed przebudową nazywa też
    tabelę wątków, która zostanie skasowana.

    Wyłapuje pytanie, które wymienia tylko kolekcję: operator nie wiedziałby, że potwierdza też
    skasowanie wątków, w których agent szuka po słowach."""
    (_corpus(tmp_path) / "anonymized").mkdir()

    result = runner.invoke(cli, ["tickets", "reindex", str(tmp_path)], input="n\n")

    assert f"tabelę '{TICKETS_TABLE}'" in result.stdout
    assert "zostaje" not in result.stdout


def test_rebuild_names_the_collection_and_table_from_the_configuration(
    tmp_path: Path, stub_run: StubRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sprawdza, czy pytanie przed przebudową nazywa kolekcję i tabelę wątków podane
    w `QDRANT_COLLECTION` i `POSTGRES_TICKETS_TABLE`, a nie domyślne (tu `tickets_golden`
    i `tickets_text_golden`, jak przy golden secie).

    Wyłapuje pytanie z nazwą zaszytą w kodzie: operator, który przebudowuje golden set obok
    instancji, potwierdzałby skasowanie tabeli instancji, nie widząc, że to nie ta."""
    monkeypatch.setenv("QDRANT_COLLECTION", "tickets_golden")
    monkeypatch.setenv("POSTGRES_TICKETS_TABLE", "tickets_text_golden")
    (_corpus(tmp_path) / "anonymized").mkdir()

    result = runner.invoke(cli, ["tickets", "reindex", str(tmp_path)], input="n\n")

    assert "kolekcję 'tickets_golden'" in result.stdout
    assert "tabelę 'tickets_text_golden'" in result.stdout


def test_rebuild_says_the_threads_table_stays_without_threads(
    tmp_path: Path, stub_run: StubRun
) -> None:
    """Sprawdza, czy przy korpusie bez `anonymized/` (jak golden set) pytanie przed przebudową
    mówi, że tabela wątków zostaje.

    Wyłapuje pytanie, które straszy skasowaniem wątków, choć przebudowa ich nie ruszy, albo
    milczy o tym, że tabela nie zostanie odbudowana."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path))], input="n\n")

    assert f"Tabela '{TICKETS_TABLE}' zostaje" in result.stdout


def test_rebuild_without_cards_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets reindex` kończy się kodem 2 i wypisuje „BŁĄD”, gdy indekser
    odmówi przebudowy, bo w katalogu nie ma kart.

    Wyłapuje komendę, która taką odmowę przepuszcza jako awarię bez czytelnego komunikatu albo
    jako sukces: operator nie wiedziałby, że wskazał pusty katalog, a skrypt wywołujący —
    że indeks nie został przebudowany."""
    stub_run.error = FileNotFoundError("brak kart w katalogu, kolekcja zostaje: /pusty")

    result = runner.invoke(cli, ["tickets", "reindex", str(tmp_path), "--yes"])

    assert result.exit_code == 2
    assert "BŁĄD" in result.output


def test_rebuild_with_yes_skips_the_prompt(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk tickets reindex --yes` kończy się kodem 0 i uruchamia indeksację
    z kasowaniem kolekcji, nie czekając na odpowiedź operatora.

    Wyłapuje komendę, która mimo `--yes` czeka na potwierdzenie: nie dałoby się jej uruchomić ze
    skryptu, bo nikt by na pytanie nie odpowiedział."""
    result = runner.invoke(cli, ["tickets", "reindex", str(_corpus(tmp_path)), "--yes"])

    assert result.exit_code == 0
    assert stub_run.calls[0]["drop_first"] is True
