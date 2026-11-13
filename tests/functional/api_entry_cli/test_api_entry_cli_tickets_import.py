from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.core_model.tickets.ticket_import_failure import TicketImportFailure
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.factory_tickets_importer import TicketsImportConfigError
from app.core_service.importer_tickets import TicketsImportAbortedError
from app.engine_anonymization import AnonymizationConfigError
from app.engine_llm import LLMConfigError
from app.entry_cli.cli import cli
from tests._helpers.tickets_import import StubImporter, StubImporterFactory
from tests._helpers.tickets_import.samples import sample_import_report

runner = CliRunner()


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> StubImporterFactory:
    """
    Description:
    Podmienia fabrykę serwisu importu w komendzie na atrapę, która zapisuje argumenty i oddaje
    atrapę serwisu.

    Example args:
        (brak)

    Example result:
        StubImporterFactory z pustymi zapisami i atrapą serwisu bez raportów
    """
    factory = StubImporterFactory()

    monkeypatch.setattr("app.entry_cli.tickets.import_.build_tickets_importer", factory.build)

    return factory


def test_the_scope_progress_and_summary_are_printed(
    tmp_path: Path, built: StubImporterFactory
) -> None:
    """Sprawdza, czy komenda wypisuje zakres (ile w eksporcie, w toku, mailowych, z kartą, do
    zrobienia, model i początek skrótu promptu), linię postępu z kosztem i szacunkiem końca co 10
    zgłoszeń i po ostatnim, ale nie po 5., oraz podsumowanie, i kończy się kodem 0.

    Wyłapuje komendę, która milczy w trakcie albo zasypuje wyjście linią na każde zgłoszenie:
    przebieg idzie godzinę w tle i tylko z tych linii widać, ile zrobiono i ile to kosztuje."""
    built.importer = StubImporter([
        sample_import_report(parsed=0),
        sample_import_report(parsed=5,  cost_usd=0.025),
        sample_import_report(parsed=10, cost_usd=0.05),
        sample_import_report(parsed=20, cost_usd=0.1),
        sample_import_report(parsed=25, cost_usd=0.125),
    ])

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Eksport: 30 zgłoszeń w raw-db/; w toku: 2, „Automat mailowy”: 2, z kartą: 1." in (
        result.output
    )
    assert "Do zrobienia: 25 (model gpt-6.1-sol, prompt 308c1c483d78)." in result.output
    assert "    5/25" not in result.output
    assert "   10/25  błędów: 0  koszt: 0.0500 USD" in result.output
    assert "   25/25  błędów: 0  koszt: 0.1250 USD" in result.output
    assert "zostało: ~" in result.output
    assert "Gotowe: 25 kart z 25 (przydatnych: 25), błędów: 0, koszt 0.1250 USD" in result.output


def test_the_summary_points_at_the_report_file(tmp_path: Path, built: StubImporterFactory) -> None:
    """Sprawdza, czy podsumowanie podaje ścieżkę pliku raportu w katalogu korpusu, z nazwą
    od chwili startu przebiegu.

    Wyłapuje podsumowanie bez ścieżki albo ze ścieżką inną niż ta, pod którą serwis zapisuje
    raport: pełnej listy błędów i rozkładu pól nie dałoby się znaleźć."""
    report         = sample_import_report(parsed=25)
    built.importer = StubImporter([report])

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert f"Raport: {TicketsCorpus(root=tmp_path).import_report_path(report.started_at)}" in (
        result.output
    )


def test_failed_tickets_exit_one_and_are_listed(tmp_path: Path, built: StubImporterFactory) -> None:
    """Sprawdza, czy przebieg z dwoma nieudanymi zgłoszeniami kończy się kodem 1, a podsumowanie
    wymienia ich numery z nazwą błędu.

    Wyłapuje komendę, która kończy się kodem 0 mimo błędów albo nie mówi, które zgłoszenia
    ponowić: potok uznałby korpus za kompletny."""
    failed = [
        TicketImportFailure(ticket_id="41003", error="LLMError"),
        TicketImportFailure(ticket_id="41004", error="AnonymizationError"),
    ]
    built.importer = StubImporter([sample_import_report(parsed=23, failed=failed)])

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 1
    assert "Błędy: 41003 (LLMError), 41004 (AnonymizationError)" in result.output


def test_nothing_to_do_says_so_and_exits_zero(tmp_path: Path, built: StubImporterFactory) -> None:
    """Sprawdza, czy przebieg bez zgłoszeń do zrobienia wypisuje „Nic do zrobienia.”, bez
    podsumowania, i kończy się kodem 0.

    Wyłapuje komendę, która przy wznowieniu skończonego korpusu wypisuje puste podsumowanie albo
    kończy się błędem: potok ponawiający import nie odróżniłby końca od awarii."""
    built.importer = StubImporter([sample_import_report(todo=0)])

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 0
    assert "Nic do zrobienia." in result.output
    assert "Gotowe" not in result.output


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TicketsImportConfigError("atrapa modelu"), id="atrapa-modelu"),
        pytest.param(LLMConfigError("brak klucza"),             id="model"),
    ],
)
def test_a_configuration_error_at_build_exits_two(
    tmp_path: Path, built: StubImporterFactory, error: Exception
) -> None:
    """Sprawdza, czy błąd konfiguracji przy budowie serwisu (atrapa modelu, brak klucza) kończy
    komendę kodem 2 z komunikatem „BŁĄD”.

    Wyłapuje komendę, która przy złej konfiguracji kończy się śladem stosu albo kodem 1: potok
    nie odróżniłby złej konfiguracji od zgłoszeń, które się nie udały i które wystarczy ponowić."""
    built.build_error = error

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 2
    assert "BŁĄD" in result.output


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NotADirectoryError("brak raw-db/"),          id="brak-eksportu"),
        pytest.param(AnonymizationConfigError("atrapa silnika"), id="anonimizator"),
        pytest.param(TicketsImportAbortedError("10 z rzędu"),    id="seria-bledow"),
    ],
)
def test_a_configuration_error_in_the_run_exits_two_and_closes(
    tmp_path: Path, built: StubImporterFactory, error: Exception
) -> None:
    """Sprawdza, czy brak `raw-db/`, błąd konfiguracji anonimizatora albo seria 10 błędów z rzędu
    w trakcie przebiegu kończy komendę kodem 2, a serwis i tak zostaje zamknięty.

    Wyłapuje komendę, która przy błędzie w przebiegu zostawia otwarte połączenia albo kończy się
    innym kodem niż przy złej konfiguracji na starcie."""
    built.importer = StubImporter(error=error)

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 2
    assert built.importer.closed is True


def test_an_interrupted_run_exits_130(tmp_path: Path, built: StubImporterFactory) -> None:
    """Sprawdza, czy przerwany przebieg (Ctrl+C) kończy się kodem 130 i mówi, że to samo
    polecenie wznowi import.

    Wyłapuje przerwanie zakończone śladem stosu bez wskazówki: operator nie wiedziałby, że karty
    zapisane do tej chwili zostają i że wystarczy uruchomić komendę ponownie."""
    built.importer = StubImporter(error=KeyboardInterrupt())

    result = runner.invoke(cli, ["tickets", "import", str(tmp_path)])

    assert result.exit_code == 130
    assert "To samo polecenie wznowi import" in result.output


def test_the_corpus_limit_and_concurrency_reach_the_service(
    tmp_path: Path, built: StubImporterFactory
) -> None:
    """Sprawdza, czy katalog podany komendzie jest korpusem serwisu, `--concurrency 2` trafia do
    fabryki, a `--limit 20` do przebiegu.

    Wyłapuje komendę, która gubi limit: próba na 20 zgłoszeniach poszłaby po cały eksport,
    czyli za cały koszt."""
    built.importer = StubImporter([sample_import_report(todo=20, parsed=20)])

    runner.invoke(
        cli, ["tickets", "import", str(tmp_path), "--limit", "20", "--concurrency", "2"]
    )

    assert built.corpora     == [TicketsCorpus(root=tmp_path)]
    assert built.concurrency == [2]
    assert built.importer.limits == [20]


def test_without_a_directory_the_configured_corpus_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: StubImporterFactory
) -> None:
    """Sprawdza, czy `helpdesk tickets import` bez katalogu bierze korpus z `TICKETS_CORPUS_DIR`
    i bez `--limit` parsuje wszystko, cztery zgłoszenia naraz.

    Wyłapuje komendę, która bez argumentu pisze gdzie indziej niż trasa zamknięcia i komendy
    indeksacji: karty z importu nie trafiłyby do indeksu."""
    monkeypatch.setenv("TICKETS_CORPUS_DIR", str(tmp_path))
    built.importer = StubImporter([sample_import_report(parsed=25)])

    runner.invoke(cli, ["tickets", "import"])

    assert built.corpora         == [TicketsCorpus(root=tmp_path)]
    assert built.concurrency     == [4]
    assert built.importer.limits == [None]


def test_the_command_is_registered_under_tickets() -> None:
    """Sprawdza, czy `helpdesk tickets --help` wymienia komendę `import`.

    Wyłapuje komendę, której nie zarejestrowano w obszarze `tickets`: plik by istniał, ale
    operator nie miałby jak jej uruchomić."""
    result = runner.invoke(cli, ["tickets", "--help"])

    assert result.exit_code == 0
    assert "import" in result.output
