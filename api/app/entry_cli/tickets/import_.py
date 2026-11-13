"""
Description:
`helpdesk tickets import` — masowy import zgłoszeń do korpusu (p. 31): zgłoszenia z eksportu zrzutu
w `raw-db/` stają się wątkami po anonimizacji i kartami w `anonymized/` i `cards/`. Woła płatny
model, więc uruchamia się świadomie, najpierw na próbę z `--limit`. Indeksów nie buduje — to robi
potem `helpdesk tickets reindex`.

Plik nazywa się `import_.py`, bo `import` to słowo kluczowe Pythona; komenda nazywa się `import`.

Przykład wyjścia (zmyślone liczby):

    Eksport: 1955 zgłoszeń w raw-db/; w toku: 61, „Automat mailowy”: 136, z kartą: 0.
    Do zrobienia: 1758 (model gpt-6.1-sol, prompt 308c1c483d78).
       10/1758  błędów: 0  koszt: 0.0512 USD  czas: 21s  zostało: ~1h 01min
       20/1758  błędów: 0  koszt: 0.1034 USD  czas: 43s  zostało: ~1h 02min
    …
    Gotowe: 1756 kart z 1758 (przydatnych: 1201), błędów: 2, koszt 9.1234 USD, czas 58min 12s.
    Błędy: 10544 (LLMError), 22817 (AnonymizationError)
    Raport: /code/data/unsafe/corpus/import-2026-11-13T10-15-00.json

O czym pamiętać przy zmianach:

- Linia postępu wychodzi co 10 zgłoszeń z kosztem i szacunkiem końca: przebieg trwa godzinę
  i idzie w tle, a ktoś czyta jego wyjście.
- Na wyjściu są wyłącznie numery, liczby i nazwy błędów, nigdy treść zgłoszeń.
- Kody wyjścia: 0 — wszystko sparsowane albo nic do zrobienia, 1 — któreś zgłoszenie się nie
  udało (to samo polecenie je ponowi), 2 — konfiguracja albo brak `raw-db/`, 130 — przerwane.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer

from app.config import Settings
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_import_report import TicketsImportReport
from app.core_service.factory_tickets_importer import (
    TicketsImportConfigError,
    build_tickets_importer,
)
from app.core_util.time import format_duration
from app.engine_anonymization import AnonymizationConfigError
from app.engine_llm import LLMConfigError
from app.entry_cli.tickets.common import CORPUS_DIR_HELP, corpus_or_default

HELP = "Sparsuj zgłoszenia z raw-db/ korpusu do wątków i kart (płatne: woła model)."

# Pomoc opcji `--limit` i `--concurrency`.
LIMIT_HELP       = "Tylko pierwsze N zgłoszeń do zrobienia, na próbę."
CONCURRENCY_HELP = "Ile zgłoszeń naraz."

# Ile zgłoszeń naraz domyślnie. Anonimizator stoi na jednym GPU: w pomiarze silnika z 2026-10-19
# przy 16 naraz jedno wywołanie padło pod obciążeniem (503).
DEFAULT_CONCURRENCY = 4

# Co ile zgłoszeń linia postępu.
PROGRESS_EVERY = 10

# Ile błędów wypisać w podsumowaniu; pełna lista jest w pliku raportu.
MAX_LISTED_FAILURES = 20

# Ile znaków skrótu promptu pokazać w terminalu; pełny jest w pliku raportu.
DIGEST_SHOWN = 12


def import_tickets(
    directory:   Path | None = typer.Argument(None, help=CORPUS_DIR_HELP),
    limit:       int | None  = typer.Option(None, "--limit", min=1, help=LIMIT_HELP),
    concurrency: int         = typer.Option(DEFAULT_CONCURRENCY, "--concurrency", min=1,
                                            help=CONCURRENCY_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets import` — parsuje zgłoszenia z eksportu do korpusu, wypisując zakres,
    postęp z kosztem i podsumowanie. Przerwany przebieg wznawia się tym samym poleceniem.

    Example args:
        directory=None  # korpus z TICKETS_CORPUS_DIR
        limit=20
        concurrency=4

    Example result:
        wypisuje zakres, postęp i podsumowanie; kod 0, gdy wszystkie zgłoszenia się udały

    Raises:
        typer.Exit: kod 1, gdy któreś zgłoszenie się nie udało; 2 przy złej konfiguracji albo
            braku `raw-db/`; 130 po przerwaniu
    """
    corpus = corpus_or_default(directory)

    try:
        report = asyncio.run(_run(corpus, limit, concurrency))
    except (
        NotADirectoryError,        # korpus bez katalogu eksportu
        TicketsImportConfigError,  # model generujący to atrapa
        LLMConfigError,            # dostawca, klucz albo model modelu generującego
        AnonymizationConfigError,  # adres anonimizatora albo jego atrapa przy prawdziwym modelu
    ) as exc:
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except KeyboardInterrupt as exc:
        # Karty zapisane do tej chwili zostają, a raport przebiegu jest już na dysku.
        typer.echo("\nPrzerwano. To samo polecenie wznowi import od zgłoszeń bez karty.")
        raise typer.Exit(code=130) from exc

    _print_summary(report, corpus)

    if report.failed:
        raise typer.Exit(code=1)


async def _run(
    corpus:      TicketsCorpus,  # np. TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
    limit:       int | None,     # np. 20
    concurrency: int,            # np. 4
) -> TicketsImportReport:
    """
    Description:
    Bierze serwis importu z fabryki, uruchamia go z drukowaniem postępu i zamyka go — także wtedy,
    gdy przebieg padnie w połowie.

    Example args:
        corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
        limit=None
        concurrency=4

    Example result:
        TicketsImportReport(todo=1758, parsed=1756, …)

    Raises:
        NotADirectoryError: korpus nie ma katalogu `raw-db/`
        TicketsImportConfigError: model generujący jest atrapą
        LLMConfigError: model generujący jest źle skonfigurowany
        AnonymizationConfigError: anonimizator odmówił z powodu konfiguracji
    """
    importer = build_tickets_importer(Settings(), corpus, concurrency)

    try:
        return await importer.run(limit, _print_progress)
    finally:
        await importer.aclose()


def _print_progress(
    report: TicketsImportReport,  # np. TicketsImportReport(todo=1758, parsed=10, …)
) -> None:
    """
    Description:
    Wypisuje zakres przebiegu, gdy serwis skończył wybierać zgłoszenia, a potem co 10 zgłoszeń
    i po ostatnim linię postępu z błędami, kosztem, czasem i szacunkiem, ile zostało.

    Example args:
        report=TicketsImportReport(todo=1758, parsed=10, cost_usd=0.0512, …)

    Example result:
        None — wypisuje „   10/1758  błędów: 0  koszt: 0.0512 USD  czas: 21s  zostało: ~1h 01min”
    """
    done = report.done

    # --- zgłoszenia wybrane, model jeszcze niewołany ---
    if done == 0:
        _print_scope(report)
        return

    if done % PROGRESS_EVERY and done != report.todo:
        return

    elapsed = (datetime.now(UTC) - report.started_at).total_seconds()
    left    = elapsed / done * (report.todo - done)

    typer.echo(
        f"{done:>5}/{report.todo}  błędów: {len(report.failed)}  "
        f"koszt: {report.cost_usd:.4f} USD  czas: {format_duration(elapsed)}  "
        f"zostało: ~{format_duration(left)}"
    )


def _print_scope(
    report: TicketsImportReport,  # np. TicketsImportReport(files=1955, todo=1758, …)
) -> None:
    """
    Description:
    Wypisuje, ile zgłoszeń jest w eksporcie, ile wypadło z zakresu i dlaczego, ile jest do
    zrobienia oraz którym modelem i promptem.

    Example args:
        report=TicketsImportReport(files=1955, skipped_open=61, skipped_mail=136, todo=1758, …)

    Example result:
        None — dwie linie zakresu na wyjściu
    """
    typer.echo(
        f"Eksport: {report.files} zgłoszeń w raw-db/; w toku: {report.skipped_open}, "
        f"„Automat mailowy”: {report.skipped_mail}, z kartą: {report.already_carded}."
    )

    if not report.todo:
        typer.echo("Nic do zrobienia.")
        return

    typer.echo(
        f"Do zrobienia: {report.todo} (model {report.model}, "
        f"prompt {report.prompt_digest[:DIGEST_SHOWN]})."
    )


def _print_summary(
    report: TicketsImportReport,  # np. TicketsImportReport(todo=1758, parsed=1756, …)
    corpus: TicketsCorpus,        # np. TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
) -> None:
    """
    Description:
    Wypisuje podsumowanie przebiegu: karty, przydatne, błędy z numerami, koszt, czas i ścieżkę
    raportu. Przy pustym przebiegu nic, bo zakres powiedział już „Nic do zrobienia”.

    Example args:
        report=TicketsImportReport(todo=1758, parsed=1756, failed=[…], …)
        corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))

    Example result:
        None — podsumowanie na wyjściu
    """
    if not report.todo:
        return

    finished = report.finished_at or datetime.now(UTC)
    elapsed  = (finished - report.started_at).total_seconds()

    typer.echo(
        f"Gotowe: {report.parsed} kart z {report.todo} (przydatnych: {report.useful}), "
        f"błędów: {len(report.failed)}, koszt {report.cost_usd:.4f} USD, "
        f"czas {format_duration(elapsed)}."
    )

    # --- błędy: kilka przykładów, pełna lista w pliku raportu ---
    if report.failed:
        shown = report.failed[:MAX_LISTED_FAILURES]
        line  = ", ".join(f"{failure.ticket_id} ({failure.error})" for failure in shown)
        more  = len(report.failed) - len(shown)

        typer.echo(f"Błędy: {line}" + (f" … i {more} więcej" if more else ""))

    typer.echo(f"Raport: {corpus.import_report_path(report.started_at)}")
