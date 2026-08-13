import asyncio
import time
from pathlib import Path

import typer

from app.config import Settings
from app.llm import LLMError, get_llm_client
from app.model.ticket_parse_result import ParseResult
from app.model.validation_parsed_report import ValidationReport
from app.service.parser_ticket_parsed import TicketParser
from app.service.parser_ticket_raw import load_raw_ticket
from app.service.validator_ticket_parsed import validate_directory
from app.util.time import format_duration

# --- helpdesk tickets -------------------------------------------------------------------------
#
# | komenda                   | co robi                                                        |
# |---------------------------|----------------------------------------------------------------|
# | `tickets validate <kat.>` | sprawdza pliki JSON wobec kontraktu ParsedTicket; exit 1 = błędy |
# | `tickets parse`           | parsuje zgłoszenia z data/raw/ przez LLM i zapisuje artefakty   |
#
# Grupa obejmuje wytwarzanie ARTEFAKTU (zasada 7) — to, co powstaje raz i drogo. Co się dzieje
# z artefaktem dalej, należy do `helpdesk rag`.
tickets = typer.Typer(
    help            = "Operacje na sparsowanych zgłoszeniach z data/parsed/.",
    no_args_is_help = True,
)

# Export files are named after the ticket, so a ticket id maps to a path without an index.
RAW_FILE_PATTERN = "zgloszenie-{ticket_id}.json"


def _print_report(report: ValidationReport, verbose: bool) -> None:
    """
    Description:
    Prints the report. Failures always appear; valid files only with `--verbose`, so a run over a
    full corpus shows the problems instead of scrolling them off the screen.

    Example args:
        report=ValidationReport(verdicts=[…])
        verbose=False

    Example result:
        None — writes the per-file lines and a summary to stdout
    """
    for verdict in report.verdicts:
        if verdict.ok:
            # A passing file is noise during a corpus run; it matters only when asked for.
            if verbose:
                typer.echo(f"OK   {verdict.path.name}")
            continue

        typer.echo(f"BŁĄD {verdict.path.name}")

        for error in verdict.errors:
            typer.echo(f"       {error}")

    checked = len(report.verdicts)
    failed  = len(report.failed)

    typer.echo(f"\nSprawdzono {checked}, błędnych {failed}.")


@tickets.command("validate", help="Sprawdź pliki JSON w katalogu wobec kontraktu ParsedTicket.")
def validate(
    directory: Path = typer.Argument(Path("data/parsed"), help="Katalog z artefaktami."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz też poprawne pliki."),
) -> None:
    """
    Description:
    Validates a directory of artifacts and exits non-zero if anything is wrong, so the command is
    usable as a gate in a pipeline and not only by a human reading the output.

    A thin adapter over `validate_directory()`: no validation logic lives here, which is what lets
    the batch import of stage 10 reuse the same check without going through the CLI.

    Example args:
        directory=Path("data/parsed")
        verbose=False

    Example result:
        prints the report; exits 0 when every file is valid, 1 otherwise

    Raises:
        typer.Exit: code 1 on invalid files, code 2 when the directory does not exist
    """
    try:
        report = validate_directory(directory)
    except NotADirectoryError as exc:
        # Exit code 2 keeps "you pointed me at nothing" apart from "the artifacts are broken" —
        # a pipeline must be able to tell a misconfiguration from a genuine failure.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_report(report, verbose)

    if not report.ok:
        raise typer.Exit(code=1)


def _resolve_sources(
    raw_dir:    Path,        # e.g. Path("data/raw")
    ticket_ids: list[str],   # e.g. ["33644", "34287"]
    limit:      int | None,  # e.g. 10
) -> list[Path]:
    """
    Description:
    Works out which export files to parse. Explicit ids win over a directory sweep, because naming
    tickets is how the comparison runs pick the SAME ten tickets for every model.

    A missing file is an error rather than a skip: silently parsing nine of ten requested tickets
    would make two runs incomparable without saying so.

    Example args:
        raw_dir=Path("data/raw")
        ticket_ids=["33644", "34287"]
        limit=None

    Example result:
        [Path("data/raw/zgloszenie-33644.json"), Path("data/raw/zgloszenie-34287.json")]

    Raises:
        typer.Exit: the directory does not exist, or a named ticket has no export file
    """
    if not raw_dir.is_dir():
        typer.echo(f"BŁĄD: nie jest katalogiem: {raw_dir}", err=True)
        raise typer.Exit(code=2)

    if ticket_ids:
        paths   = [raw_dir / RAW_FILE_PATTERN.format(ticket_id=t) for t in ticket_ids]
        missing = [path.name for path in paths if not path.is_file()]

        if missing:
            typer.echo(f"BŁĄD: brak plików źródłowych: {', '.join(missing)}", err=True)
            raise typer.Exit(code=2)

        return paths

    paths = sorted(raw_dir.glob("zgloszenie-*.json"))

    return paths[:limit] if limit is not None else paths


def _print_parse_summary(results: list[ParseResult], out_dir: Path) -> None:
    """
    Description:
    Prints the run total. Cost is reported in dollars because that is the unit anyone budgeting a
    corpus run thinks in; token counts stay alongside it so the number can be checked.

    Failures are counted separately from cost on purpose — a rejected answer was still paid for,
    and hiding that would understate what a re-run costs.

    Example args:
        results=[ParseResult(ticket_id="33644", cost_usd=0.008, …)]
        out_dir=Path("data/parsed/haiku")

    Example result:
        None — writes the summary to stdout
    """
    parsed = [result for result in results if result.ok]
    failed = [result for result in results if not result.ok]

    total_cost   = sum(result.cost_usd for result in results)
    total_input  = sum(result.prompt_tokens for result in results)
    total_output = sum(result.completion_tokens for result in results)

    typer.echo("")
    typer.echo(f"Sparsowano {len(parsed)}/{len(results)}, zapisano do {out_dir}")

    if failed:
        typer.echo(f"Nieudane: {', '.join(result.ticket_id for result in failed)}")

    typer.echo(f"Tokeny: {total_input} wejścia, {total_output} wyjścia")
    # Six decimal places: a single Haiku ticket costs ~$0.008, so two would round to $0.01 and a
    # ten-ticket run would look free.
    typer.echo(f"Koszt przebiegu: ${total_cost:.6f}")

    total_seconds = sum(result.latency_ms for result in results) / 1000

    typer.echo(f"Czas przebiegu: {format_duration(total_seconds)}")

    if parsed:
        typer.echo(f"Średnio na zgłoszenie: ${total_cost / len(results):.6f}"
                   f", {format_duration(total_seconds / len(results))}")


async def _parse_all(
    parser:  TicketParser,  # e.g. TicketParser(llm=ClaudeLLMClient(…))
    paths:   list[Path],    # e.g. [Path("data/raw/zgloszenie-33644.json")]
    out_dir: Path,          # e.g. Path("data/parsed/haiku")
) -> list[ParseResult]:
    """
    Description:
    Parses every source file and writes each artifact as soon as it validates.

    Sequential and write-as-you-go on purpose: the LLM run is the expensive, one-off step (rule 7),
    so an interrupted run must keep everything it already paid for. Parallelism would buy wall
    clock at the cost of rate limits and a much messier progress report.

    Example args:
        parser=TicketParser(llm=…)
        paths=[Path("data/raw/zgloszenie-33644.json")]
        out_dir=Path("data/parsed/haiku")

    Example result:
        [ParseResult(ticket_id="33644", ticket=ParsedTicket(…), cost_usd=0.0080)]

    Raises:
        typer.Exit: the provider failed (timeout, no connection, refusal) — reported with what the
            run cost up to that point, so the operator knows what was already spent
    """
    results: list[ParseResult] = []
    started_at = time.perf_counter()

    for index, path in enumerate(paths, start=1):
        raw = load_raw_ticket(path)

        # Thread size announced BEFORE the call, and the line is flushed without a newline. On a
        # local model one ticket takes minutes, so a bare counter would read as a hung process —
        # the character count is the only advance warning of which ones will be slow.
        thread_chars = len(raw.as_thread())

        typer.echo(f"[{index}/{len(paths)}] {raw.ticket_id} ({thread_chars:,} zn.) … ", nl=False)

        try:
            result = await parser.parse(raw)
        except LLMError as exc:
            # Stop, but not silently: everything parsed so far is already on disk and paid for.
            typer.echo("BŁĄD")
            typer.echo(f"\nPrzerwano na zgłoszeniu {raw.ticket_id}: {exc}", err=True)
            _print_parse_summary(results, out_dir)
            raise typer.Exit(code=1) from exc

        results.append(result)

        if not result.ok:
            typer.echo("odrzucone")

            for error in result.errors:
                typer.echo(f"      {error}")

            continue

        target = out_dir / f"{result.ticket_id}.json"
        target.write_text(
            result.ticket.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

        # Elapsed total after every ticket, because on a slow provider the useful question is not
        # "what did this one cost" but "how long until this finishes".
        elapsed_total = time.perf_counter() - started_at

        typer.echo(
            f"ok  (${result.cost_usd:.6f}, {result.latency_ms / 1000:.1f}s"
            f", razem {format_duration(elapsed_total)})"
        )

    return results


@tickets.command("parse", help="Sparsuj zgłoszenia z data/raw/ przez LLM i zapisz artefakty.")
def parse(
    out_dir: Path = typer.Argument(..., help="Katalog docelowy na artefakty."),
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir", help="Katalog ze zgłoszeniami."),
    ticket:  list[str] = typer.Option(
        [], "--ticket", "-t", help="Numer zgłoszenia; wielokrotnie. Pusto = cały katalog."
    ),
    limit:   int | None = typer.Option(None, "--limit", help="Ile zgłoszeń z katalogu (bez -t)."),
    model:   str | None = typer.Option(None, "--model", help="Nadpisz LLM_MODEL na ten przebieg."),
) -> None:
    """
    Description:
    Parses source tickets into artifacts and reports what the run cost.

    A thin adapter over `TicketParser`: it resolves paths, prints and sets the exit code, and holds
    no parsing logic — which is what lets the batch import of stage 10 reuse the same parser.

    `--model` overrides the configured model for one run, so comparing two models is two commands
    rather than two edits of `.env`.

    Example args:
        out_dir=Path("data/parsed/haiku")
        ticket=["33644", "34287"]
        model="claude-haiku-4-5"

    Example result:
        writes one JSON per ticket, prints per-ticket progress and the run total; exits 0 when
        every ticket parsed, 1 when any was rejected

    Raises:
        typer.Exit: bad paths (2), a rejected ticket or a provider failure (1)
    """
    paths = _resolve_sources(raw_dir, ticket, limit)

    if not paths:
        typer.echo(f"BŁĄD: brak zgłoszeń do sparsowania w {raw_dir}", err=True)
        raise typer.Exit(code=2)

    settings = Settings()

    # An override reaches the client the same way the configured value does — through Settings —
    # so the factory keeps its single source of truth and its fail-fast on an unpriced model.
    if model is not None:
        settings = settings.model_copy(update={"llm_model": model})

    out_dir.mkdir(parents=True, exist_ok=True)

    # The offline fake has no model name; printing "None" there would read like a misconfiguration.
    named_model = settings.llm_model or "(bez modelu)"

    typer.echo(f"Model: {named_model} ({settings.llm_provider})")
    typer.echo(f"Zgłoszeń do sparsowania: {len(paths)}\n")

    results = asyncio.run(_parse_all(TicketParser(get_llm_client(settings)), paths, out_dir))

    _print_parse_summary(results, out_dir)

    if any(not result.ok for result in results):
        raise typer.Exit(code=1)
