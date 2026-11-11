import asyncio
from pathlib import Path

import typer

from app.config import Settings
from app.core_model.tickets.tickets_index_report import TicketsIndexReport
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.db_qdrant import DbQdrantError
from app.engine_embedding import EmbeddingError

# Wspólne dla `tickets index` i `tickets reindex` — różni je wyłącznie to, czy kolekcja jest
# najpierw kasowana.

# Pomoc argumentu z katalogiem kart, wspólna dla `validate`, `index` i `reindex`.
CARDS_DIR_HELP = "Katalog z kartami; bez niego cards/ korpusu z TICKETS_CORPUS_DIR."

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


def cards_dir_or_default(
    directory: Path | None,  # np. None — komenda bez katalogu
) -> Path:
    """
    Description:
    Zwraca katalog kart dla komendy: podany wprost albo, gdy go nie podano, `cards/` korpusu
    z konfiguracji (`TICKETS_CORPUS_DIR`). Wspólne dla `validate`, `index` i `reindex`, żeby
    wszystkie trzy bez argumentu patrzyły w to samo miejsce.

    Example args:
        directory=None

    Example result:
        Path("/code/data/unsafe/corpus/cards")
    """
    if directory is not None:
        return directory

    return Settings().tickets_corpus().cards_dir


async def _run(
    directory:  Path,  # np. Path("data/unsafe/corpus/cards")
    drop_first: bool,  # np. True — przebudowa zamiast budowy
) -> TicketsIndexReport:
    """
    Description:
    Bierze indekser z fabryki, uruchamia indeksację i zamyka połączenia — także wtedy, gdy
    przebieg padnie w połowie.

    Example args:
        directory=Path("data/unsafe/corpus/cards")
        drop_first=False

    Example result:
        TicketsIndexReport(read=200, indexed=171, …)

    Raises:
        NotADirectoryError: katalog z artefaktami nie istnieje
        FileNotFoundError: przebudowa na katalogu bez kart
        EmbeddingError: embedder nieosiągalny albo odpowiedział błędem
        DbQdrantError: Qdrant nieosiągalny albo odrzucił zapis
    """
    indexer = build_tickets_indexer(Settings())

    try:
        if drop_first:
            return await indexer.rebuild(directory)

        return await indexer.build(directory)
    finally:
        await indexer.aclose()


def execute_index_build(
    directory:  Path,  # np. Path("data/unsafe/corpus/cards")
    drop_first: bool,  # np. False
    verbose:    bool,  # np. False
) -> None:
    """
    Description:
    Wykonuje jeden przebieg indeksacji i go wypisuje, zamieniając każdą porażkę na kod wyjścia.
    Wspólne dla `tickets index` i `tickets reindex`.

    Example args:
        directory=Path("data/unsafe/corpus/cards")
        drop_first=False
        verbose=False

    Example result:
        None — wypisuje raport; kod wyjścia niezerowy przy porażce

    Raises:
        typer.Exit: kod 2 przy braku katalogu, przebudowie bez kart albo nieosiągalnej usłudze,
            kod 1, gdy nic nie zaindeksowano
    """
    try:
        report = asyncio.run(_run(directory, drop_first))
    except NotADirectoryError as exc:
        # Kod 2 oddziela „wskazałeś nic" od „przebieg nic nie dał" — potok musi odróżnić złą
        # konfigurację od rzeczywiście pustego wyniku.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except FileNotFoundError as exc:
        # Przebudowa na katalogu bez kart: indekser odmówił, zanim cokolwiek skasował, więc
        # kolekcja stoi nietknięta — to też „wskazałeś nic”.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (EmbeddingError, DbQdrantError) as exc:
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
