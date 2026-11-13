import asyncio
from pathlib import Path

import typer

from app.config import Settings
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_index_report import TicketsIndexReport
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from app.engine_embedding import EmbeddingError

# Wspólne dla `tickets index` i `tickets reindex` — różni je wyłącznie to, czy indeksy są
# najpierw kasowane.

# Pomoc argumentu z katalogiem korpusu, wspólna dla `validate`, `index`, `reindex` i `import`.
CORPUS_DIR_HELP = "Katalog korpusu (raw-db/, anonymized/, cards/); bez niego TICKETS_CORPUS_DIR."

# Pomoc flagi `--verbose` w `index` i `reindex`.
VERBOSE_DROPS_HELP = "Wypisz wszystkie odrzucone."

# Ile odrzuconych zgłoszeń wypisać, zanim lista zostanie ucięta. Pełna lista należy do pliku
# raportu, nie do terminala — ale kilka przykładów sprawia, że odsetek odrzuceń jest wiarygodny.
MAX_LISTED_DROPS = 10


def _print_report(
    report:  TicketsIndexReport,  # np. TicketsIndexReport(read=200, indexed=171, …)
    verbose: bool,              # np. False
) -> None:
    """
    Description:
    Wypisuje, co zrobił przebieg: liczby, rozbicie odrzuceń wg powodu, przykłady i ostrzeżenia.

    Rozbicie to nie ozdoba — filtr, który po cichu przepoławia indeks, wygląda dokładnie jak
    działający, i to jedyne miejsce, gdzie tę różnicę widać (CLAUDE.md -> etap 4).

    Example args:
        report=TicketsIndexReport(read=200, indexed=171, …)
        verbose=False

    Example result:
        None — podsumowanie na stdout
    """
    typer.echo("")
    typer.echo(
        f"Wczytano {report.read}, zaindeksowano {report.indexed}, odrzucono {report.dropped}."
    )

    # --- tabela wątków: zapisana albo świadomie pominięta ---
    if report.threads is None:
        typer.echo("Korpus bez katalogu anonymized/: tabela wątków bez zmian.")
    else:
        typer.echo(f"Wątków w tabeli: {report.threads}.")

    # --- dlaczego rekordy odpadły ---
    by_reason = report.filtered.by_reason()

    if by_reason:
        typer.echo("\nOdrzucone wg powodu:")

        for reason, count in by_reason.items():
            typer.echo(f"  {reason}: {count}")
            ticket_ids = report.filtered.ticket_ids_for(reason)
            shown      = ticket_ids if verbose else ticket_ids[:MAX_LISTED_DROPS]

            typer.echo(f"       {', '.join(shown)}")

            # Powiedz, że lista jest ucięta, zamiast pozwolić jej wyglądać na pełną.
            if len(shown) < len(ticket_ids):
                typer.echo(f"       … i {len(ticket_ids) - len(shown)} więcej (--verbose)")

    # --- wszystko, co przebieg chce pokazać operatorowi ---
    for warning in report.warnings:
        typer.echo(f"\nUWAGA: {warning}")


def corpus_or_default(
    directory: Path | None,  # np. None — komenda bez katalogu
) -> TicketsCorpus:
    """
    Description:
    Zwraca korpus dla komendy: z podanego katalogu albo, gdy go nie podano, z konfiguracji
    (`TICKETS_CORPUS_DIR`). Wspólne dla `validate`, `index` i `reindex`, żeby wszystkie trzy bez
    argumentu patrzyły w to samo miejsce.

    Example args:
        directory=Path("data/unsafe/golden")

    Example result:
        TicketsCorpus(root=Path("data/unsafe/golden"))
    """
    if directory is not None:
        return TicketsCorpus(root=directory)

    return Settings().tickets_corpus()


async def _run(
    corpus:     TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
    drop_first: bool,           # np. True — przebudowa zamiast budowy
) -> TicketsIndexReport:
    """
    Description:
    Bierze indekser z fabryki, uruchamia indeksację i zamyka połączenia — także wtedy, gdy
    przebieg padnie w połowie.

    Example args:
        corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))
        drop_first=False

    Example result:
        TicketsIndexReport(read=200, indexed=171, threads=171, …)

    Raises:
        NotADirectoryError: katalog kart nie istnieje
        FileNotFoundError: przebudowa bez kart albo karta bez wątku w `anonymized/`
        EmbeddingError: embedder nieosiągalny albo odpowiedział błędem
        DbQdrantError: Qdrant nieosiągalny albo odrzucił zapis
        DbPostgresError: Postgres nieosiągalny albo odrzucił zapis
    """
    indexer = build_tickets_indexer(Settings())

    try:
        if drop_first:
            return await indexer.rebuild(corpus)

        return await indexer.build(corpus)
    finally:
        await indexer.aclose()


def execute_index_build(
    corpus:     TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
    drop_first: bool,           # np. False
    verbose:    bool,           # np. False
) -> None:
    """
    Description:
    Wykonuje jeden przebieg indeksacji i go wypisuje, zamieniając każdą porażkę na kod wyjścia.
    Wspólne dla `tickets index` i `tickets reindex`.

    Example args:
        corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))
        drop_first=False
        verbose=False

    Example result:
        None — wypisuje raport; kod wyjścia niezerowy przy porażce

    Raises:
        typer.Exit: kod 2 przy braku katalogu kart, przebudowie bez kart, karcie bez wątku albo
            nieosiągalnej usłudze, kod 1, gdy nic nie zaindeksowano
    """
    try:
        report = asyncio.run(_run(corpus, drop_first))
    except NotADirectoryError as exc:
        # Kod 2 oddziela „wskazałeś nic" od „przebieg nic nie dał" — potok musi odróżnić złą
        # konfigurację od rzeczywiście pustego wyniku.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except FileNotFoundError as exc:
        # Przebudowa bez kart albo karta bez wątku: indekser odmówił, zanim cokolwiek zapisał
        # albo skasował, więc indeksy stoją nietknięte — korpus trzeba najpierw poprawić.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (EmbeddingError, DbQdrantError, DbPostgresError) as exc:
        # Leżąca zależność to też 2: ponowienie tej samej komendy może zadziałać, pusty korpus
        # sam się nie naprawi.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_report(report, verbose)

    # Pusty indeks nigdy nie jest sukcesem: znaczy, że zepsuty jest korpus, filtr albo okablowanie,
    # a kod 0 pozwoliłby zaplanowanej przebudowie zniszczyć działający indeks niezauważenie.
    if report.indexed == 0:
        typer.echo("\nBŁĄD: nie zaindeksowano żadnego rekordu.", err=True)
        raise typer.Exit(code=1)
