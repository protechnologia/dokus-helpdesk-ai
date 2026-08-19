import asyncio
from datetime import date
from pathlib import Path

import typer

from app.config import Settings
from app.embedding import EmbeddingClient, EmbeddingError
from app.factory import build_searcher
from app.llm import LLMError
from app.model.rag_index_report import IndexBuildReport
from app.model.rag_search_result import SearchResult
from app.model.ticket_raw import RawTicket
from app.retrieval import QdrantClient, RetrievalError
from app.service.rag_indexer import TicketIndexer
from app.service.rag_searcher import SearchParseError

# --- helpdesk rag ---------------------------------------------------------------------------
#
# | komenda                 | co robi                                                     |
# |-------------------------|-------------------------------------------------------------|
# | `rag index <katalog>`   | dokłada artefakty do kolekcji, nadpisując punkty tych samych |
# | `rag reindex <katalog>` | kasuje kolekcję i buduje ją od zera (pyta o potwierdzenie)   |
# | `rag search "treść"`    | szuka podobnych zgłoszeń (parsuje zapytanie LLM-em)          |
#
# Grupa zbiera to, co obsługuje nogę 1 (wykorzystanie bazy wiedzy) — dołączą tu wyszukiwanie
# i generacja z etapów 5-6. Bramki i „Popraw" tu NIE trafią: z definicji działają bez indeksu.
rag = typer.Typer(
    help            = "RAG: baza wektorowa, wyszukiwanie i generacja propozycji.",
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


def _print_hits(result: SearchResult) -> None:
    """
    Description:
    Prints what the search found: how the query was read, then the hits with their scores.

    The parsed query is printed FIRST and unconditionally. A surprising hit list is explained by
    an unexpected reading of the ticket far more often than by the search itself, and on a
    terminal that reading is otherwise invisible.

    Example args:
        result=SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

    Example result:
        None — writes the hits to stdout
    """
    query = result.query

    typer.echo("")
    typer.echo("Zapytanie zrozumiane jako:")
    typer.echo(f"  problem:   {query.problem}")
    typer.echo(f"  objawy:    {query.symptoms}")
    typer.echo(f"  komponent: {query.component}")

    # An empty result is an ANSWER, not a failure: "new kind of problem" is correct for a large
    # part of this corpus, so it is stated plainly rather than left as silence.
    if result.is_empty:
        typer.echo("\nBrak trafień — nowy typ problemu.")

        # Without this the operator cannot tell an empty index from a threshold that cut it.
        if result.dropped_below_threshold:
            typer.echo(
                f"({result.dropped_below_threshold} trafień odrzucono progiem RAG_SCORE_MIN)"
            )

        return

    typer.echo(f"\nZnaleziono {len(result.hits)}:")

    for hit in result.hits:
        payload = hit.payload

        typer.echo(f"\n  [{hit.score:.3f}] zgłoszenie {hit.ticket_id} ({payload.get('date', '')})")
        typer.echo(f"      problem:     {payload.get('problem', '')}")
        typer.echo(f"      przyczyna:   {payload.get('cause', '')}")
        typer.echo(f"      rozwiązanie: {payload.get('solution', '')}")

    if result.dropped_below_threshold:
        typer.echo(f"\nOdrzucono progiem: {result.dropped_below_threshold}")


async def _run_search(
    text: str,  # e.g. "Nie mogę wysłać pisma przez ePUAP"
) -> SearchResult:
    """
    Description:
    Runs one search and releases the connections afterwards.

    The service comes from `build_searcher()`, the same construction the HTTP handler uses — a
    second assembly here would drift apart the moment a setting is added, and a CLI searching with
    different parameters than the API is a divergence nothing would report. Built rather than
    taken from `get_searcher()`, because that one is cached for the life of the process: closing a
    cached instance would leave the next caller with dead connection pools.

    Example args:
        text="Nie mogę wysłać pisma przez ePUAP"

    Example result:
        SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

    Raises:
        SearchParseError: the model's answer did not validate as a ticket
        LLMError: the provider itself failed
        EmbeddingError: the embedder is unreachable or answered with an error
        RetrievalError: Qdrant is unreachable or answered with an error
    """
    searcher = build_searcher(Settings())

    # Console query: no ticket id or thread to speak of, so the id says where it came from and the
    # date is today. Both travel into the artifact untouched by the model (identity comes from the
    # source), so a recognisable placeholder beats a fabricated number.
    raw = RawTicket(
        ticket_id = "cli",
        date      = date.today(),
        category  = "",
        subject   = "",
        body      = text,
    )

    try:
        return await searcher.search(raw)
    finally:
        await searcher.aclose()


@rag.command("search", help="Znajdź zgłoszenia podobne do podanej treści.")
def search(
    text: str = typer.Argument(..., help="Treść nowego zgłoszenia."),
) -> None:
    """
    Description:
    Searches the index for tickets resembling the given text, parsing it with the same prompt the
    corpus was parsed with.

    Costs one LLM call per run — the query is parsed before it is embedded, because a raw mail
    carries greetings and signatures that pollute the query vector.

    Example args:
        text="Nie mogę wysłać pisma przez ePUAP, błąd komunikacji"

    Example result:
        prints the parsed query and the hits; exits 0 even when nothing was found

    Raises:
        typer.Exit: code 2 for an unreachable dependency or an unparseable query
    """
    try:
        result = asyncio.run(_run_search(text))
    except SearchParseError as exc:
        # Exit 2, like an unreachable service: both mean "this run could not answer", as opposed
        # to "the corpus has nothing" — which is a legitimate result and exits 0.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except (LLMError, EmbeddingError, RetrievalError) as exc:
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_hits(result)


@rag.command("index", help="Zbuduj indeks z artefaktów, nie kasując istniejącej kolekcji.")
def index(
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


@rag.command("reindex", help="Skasuj kolekcję i zbuduj ją od zera.")
def reindex(
    directory: Path = typer.Argument(Path("data/parsed"), help="Katalog z artefaktami."),
    yes:       bool = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz wszystkie odrzucone."),
) -> None:
    """
    Description:
    Drops the collection and rebuilds it from the artifacts.

    Asks before destroying anything unless `--yes` is given. The index is rebuildable from
    `data/parsed/` by this very command (rule 8), so the risk is downtime rather than data loss —
    but an accidental run against an empty or wrong directory leaves nothing to search.

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
