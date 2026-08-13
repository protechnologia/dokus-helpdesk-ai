import asyncio
from pathlib import Path

import typer

from app.config import Settings
from app.embedding import EmbeddingClient, EmbeddingError
from app.model.rag_index_report import IndexBuildReport
from app.retrieval import QdrantClient, RetrievalError
from app.service.rag_indexer import TicketIndexer

index = typer.Typer(
    help            = "Budowa i odbudowa indeksu Qdranta z data/parsed/.",
    no_args_is_help = True,
)

# How many dropped tickets are listed before the output is cut short. The full list belongs in a
# report file, not on a terminal — but a handful of examples is what makes a drop rate believable.
MAX_LISTED_DROPS = 10


def _print_report(report: IndexBuildReport, verbose: bool) -> None:
    """
    Description:
    Prints what the run did: counts, the per-reason breakdown of drops, examples, and warnings.

    The breakdown is not decoration — a filter that silently halves the index looks exactly like
    one that works, and this is the only place that difference shows up (CLAUDE.md -> stage 4.2).

    Example args:
        report=IndexBuildReport(read=200, indexed=171, …)
        verbose=False

    Example result:
        None — writes the summary to stdout
    """
    typer.echo("")
    typer.echo(
        f"Wczytano {report.read}, zaindeksowano {report.indexed}, odrzucono {report.dropped}."
    )

    # --- why records were dropped ---
    by_reason = report.filtered.by_reason()

    if by_reason:
        typer.echo("\nOdrzucone wg powodu:")

        for reason, count in by_reason.items():
            typer.echo(f"  {reason}: {count}")
            ticket_ids = report.filtered.ticket_ids_for(reason)
            shown      = ticket_ids if verbose else ticket_ids[:MAX_LISTED_DROPS]

            typer.echo(f"       {', '.join(shown)}")

            # Say that the list was cut, rather than letting it look complete.
            if len(shown) < len(ticket_ids):
                typer.echo(f"       … i {len(ticket_ids) - len(shown)} więcej (--verbose)")

    # --- anything the run wants the operator to notice ---
    for warning in report.warnings:
        typer.echo(f"\nUWAGA: {warning}")


async def _run(
    directory: Path,  # e.g. Path("data/parsed")
    drop_first: bool, # e.g. True — rebuild rather than build
) -> IndexBuildReport:
    """
    Description:
    Builds the clients from `Settings`, runs the indexer and closes the connections.

    Both clients are closed in a `finally`: an indexing run that dies mid-way would otherwise leave
    open sockets and make the test suite warn about unclosed transports.

    Example args:
        directory=Path("data/parsed")
        drop_first=False

    Example result:
        IndexBuildReport(read=200, indexed=171, …)

    Raises:
        NotADirectoryError: the artifact directory does not exist
        EmbeddingError: the embedder is unreachable or answered with an error
        RetrievalError: Qdrant is unreachable or rejected the write
    """
    settings = Settings()
    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url   = settings.qdrant_url,
        collection = settings.qdrant_collection,
        timeout    = settings.qdrant_timeout_seconds,
    )
    indexer = TicketIndexer(
        embedder    = embedder,
        qdrant      = qdrant,
        vector_size = settings.embedding_vector_size,
    )

    try:
        if drop_first:
            return await indexer.rebuild(directory)

        return await indexer.build(directory)
    finally:
        await embedder.aclose()
        await qdrant.aclose()


def _execute(
    directory:  Path,  # e.g. Path("data/parsed")
    drop_first: bool,  # e.g. False
    verbose:    bool,  # e.g. False
) -> None:
    """
    Description:
    Runs one indexing pass and prints it, turning every failure into an exit code. Shared by both
    commands, which differ only in whether the collection is dropped first.

    Example args:
        directory=Path("data/parsed")
        drop_first=False
        verbose=False

    Example result:
        None — prints the report; exits non-zero on failure

    Raises:
        typer.Exit: code 2 for a missing directory or unreachable service, code 1 when nothing
            was indexed
    """
    try:
        report = asyncio.run(_run(directory, drop_first))
    except NotADirectoryError as exc:
        # Exit 2 keeps "you pointed me at nothing" apart from "the run produced nothing" — a
        # pipeline has to tell a misconfiguration from a genuine empty result.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (EmbeddingError, RetrievalError) as exc:
        # A dependency being down is also a 2: retrying the same command may well work, whereas an
        # empty corpus will not fix itself.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_report(report, verbose)

    # An empty index is never a success: it means the corpus, the filter or the wiring is broken,
    # and a zero exit code would let a scheduled rebuild destroy a working index unnoticed.
    if report.indexed == 0:
        typer.echo("\nBŁĄD: nie zaindeksowano żadnego rekordu.", err=True)
        raise typer.Exit(code=1)


@index.command("build", help="Zbuduj indeks z artefaktów, nie kasując istniejącej kolekcji.")
def build(
    directory: Path = typer.Argument(Path("data/parsed"), help="Katalog z artefaktami."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz wszystkie odrzucone."),
) -> None:
    """
    Description:
    Indexes artifacts into the existing collection, overwriting points of tickets already there.
    Re-running it is safe: point ids are derived from `ticket_id`, so the same ticket lands on the
    same point instead of being duplicated.

    Example args:
        directory=Path("data/parsed")
        verbose=False

    Example result:
        prints the run report; exits 0 when at least one record was indexed
    """
    _execute(directory, drop_first=False, verbose=verbose)


@index.command("rebuild", help="Skasuj kolekcję i zbuduj ją od zera.")
def rebuild(
    directory: Path = typer.Argument(Path("data/parsed"), help="Katalog z artefaktami."),
    yes:       bool = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz wszystkie odrzucone."),
) -> None:
    """
    Description:
    Drops the collection and rebuilds it from the artifacts.

    Asks before destroying anything unless `--yes` is given. The index is rebuildable from
    `data/parsed/` by this very command (rule 8), so the risk is downtime rather than data loss —
    but an accidental rebuild against an empty or wrong directory leaves nothing to search.

    Example args:
        directory=Path("data/parsed")
        yes=False
        verbose=False

    Example result:
        prints the run report; exits 0 when at least one record was indexed

    Raises:
        typer.Exit: code 1 when the operator declines the confirmation
    """
    settings = Settings()

    # The collection name comes from configuration, so the prompt states WHICH one is about to go —
    # confirming a destructive action without naming its target is how the wrong index gets wiped.
    if not yes and not typer.confirm(f"Skasować kolekcję '{settings.qdrant_collection}'?"):
        typer.echo("Przerwano.")
        raise typer.Exit(code=1)

    _execute(directory, drop_first=True, verbose=verbose)
