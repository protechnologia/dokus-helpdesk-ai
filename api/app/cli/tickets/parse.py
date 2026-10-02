import asyncio
import time
from pathlib import Path

import typer

from app.config import Settings
from app.llm import LLMError, get_llm_client
from app.model.ticket_parse_result import ParseResult
from app.service.parser_ticket_parsed import TicketParser
from app.service.parser_ticket_raw import load_raw_ticket
from app.util.time import format_duration

HELP = "Sparsuj zgłoszenia z data/raw/ przez LLM i zapisz artefakty."

# Pliki eksportu nazywają się od zgłoszenia, więc numer zgłoszenia przechodzi w ścieżkę bez indeksu.
RAW_FILE_PATTERN = "zgloszenie-{ticket_id}.json"


def _resolve_sources(
    raw_dir:    Path,        # np. Path("data/raw")
    ticket_ids: list[str],   # np. ["33644", "34287"]
    limit:      int | None,  # np. 10
) -> list[Path]:
    """
    Description:
    Ustala, które pliki eksportu sparsować. Jawne numery wygrywają z przeglądem katalogu, bo
    nazwanie zgłoszeń to sposób, w jaki przebiegi porównawcze biorą TE SAME dziesięć zgłoszeń dla
    każdego modelu.

    Brakujący plik to błąd, nie pominięcie: ciche sparsowanie dziewięciu z dziesięciu zamówionych
    zgłoszeń zrobiłoby z dwóch przebiegów nieporównywalne, nie mówiąc o tym.

    Example args:
        raw_dir=Path("data/raw")
        ticket_ids=["33644", "34287"]
        limit=None

    Example result:
        [Path("data/raw/zgloszenie-33644.json"), Path("data/raw/zgloszenie-34287.json")]

    Raises:
        typer.Exit: katalog nie istnieje albo wskazane zgłoszenie nie ma pliku eksportu
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


def _print_parse_summary(
    results: list[ParseResult],  # np. [ParseResult(ticket_id="33644", cost_usd=0.008, …)]
    out_dir: Path,               # np. Path("data/parsed/haiku")
) -> None:
    """
    Description:
    Wypisuje podsumowanie przebiegu. Koszt w dolarach, bo w tej jednostce myśli każdy, kto
    budżetuje przebieg po korpusie; liczby tokenów obok, żeby dało się go sprawdzić.

    Porażki liczone osobno od kosztu celowo — odrzucona odpowiedź też była opłacona, a ukrycie
    tego zaniżałoby koszt ponownego przebiegu.

    Example args:
        results=[ParseResult(ticket_id="33644", cost_usd=0.008, …)]
        out_dir=Path("data/parsed/haiku")

    Example result:
        None — podsumowanie na stdout
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
    # Sześć miejsc po przecinku: jedno zgłoszenie na Haiku kosztuje ~$0.008, więc przy dwóch
    # zaokrągliłoby się do $0.01, a przebieg na dziesięciu zgłoszeniach wyglądałby na darmowy.
    typer.echo(f"Koszt przebiegu: ${total_cost:.6f}")

    total_seconds = sum(result.latency_ms for result in results) / 1000

    typer.echo(f"Czas przebiegu: {format_duration(total_seconds)}")

    if parsed:
        typer.echo(f"Średnio na zgłoszenie: ${total_cost / len(results):.6f}"
                   f", {format_duration(total_seconds / len(results))}")


async def _parse_all(
    parser:  TicketParser,  # np. TicketParser(llm=ClaudeLLMClient(…))
    paths:   list[Path],    # np. [Path("data/raw/zgloszenie-33644.json")]
    out_dir: Path,          # np. Path("data/parsed/haiku")
) -> list[ParseResult]:
    """
    Description:
    Parsuje każdy plik źródłowy i zapisuje artefakt, gdy tylko przejdzie walidację.

    Po kolei i z zapisem na bieżąco celowo: przebieg LLM to drogi, jednorazowy krok (zasada 7),
    więc przerwany przebieg musi zachować wszystko, za co już zapłacono. Równoległość kupiłaby
    czas kosztem limitów zapytań i dużo bardziej zagmatwanego postępu.

    Example args:
        parser=TicketParser(llm=…)
        paths=[Path("data/raw/zgloszenie-33644.json")]
        out_dir=Path("data/parsed/haiku")

    Example result:
        [ParseResult(ticket_id="33644", ticket=ParsedTicket(…), cost_usd=0.0080)]

    Raises:
        typer.Exit: zawiódł dostawca (timeout, brak połączenia, odmowa) — z podsumowaniem tego,
            ile przebieg kosztował do tej chwili, żeby operator wiedział, co już wydano
    """
    results: list[ParseResult] = []
    started_at = time.perf_counter()

    for index, path in enumerate(paths, start=1):
        raw = load_raw_ticket(path)

        # Rozmiar wątku ogłaszany PRZED wywołaniem, linia bez nowej linii. Na modelu lokalnym jedno
        # zgłoszenie trwa minuty, więc goły licznik wyglądałby jak zawieszony proces — liczba znaków
        # to jedyne ostrzeżenie, które będą wolne.
        thread_chars = len(raw.as_thread())

        typer.echo(f"[{index}/{len(paths)}] {raw.ticket_id} ({thread_chars:,} zn.) … ", nl=False)

        try:
            result = await parser.parse(raw)
        except LLMError as exc:
            # Stop, ale nie po cichu: wszystko sparsowane do tej pory jest już na dysku i opłacone.
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

        # Łączny czas po każdym zgłoszeniu, bo przy wolnym dostawcy pytanie brzmi nie „ile
        # kosztowało to jedno", tylko „ile jeszcze do końca".
        elapsed_total = time.perf_counter() - started_at

        typer.echo(
            f"ok  (${result.cost_usd:.6f}, {result.latency_ms / 1000:.1f}s"
            f", razem {format_duration(elapsed_total)})"
        )

    return results


def parse_tickets(
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
    `helpdesk tickets parse` — parsuje zgłoszenia źródłowe na artefakty i podaje koszt przebiegu.

    Cienki adapter nad `TicketParser`: ustala ścieżki, wypisuje i ustawia kod wyjścia, bez logiki
    parsowania — dzięki temu masowy import (p. 31) użyje tego samego parsera.

    `--model` nadpisuje skonfigurowany model na jeden przebieg, więc porównanie dwóch modeli to
    dwie komendy, a nie dwie edycje `.env`.

    Example args:
        out_dir=Path("data/parsed/haiku")
        ticket=["33644", "34287"]
        model="claude-haiku-4-5"

    Example result:
        jeden JSON na zgłoszenie, postęp per zgłoszenie i podsumowanie; kod 0, gdy wszystkie
        sparsowano, 1, gdy któreś odrzucono

    Raises:
        typer.Exit: złe ścieżki (2), odrzucone zgłoszenie albo awaria dostawcy (1)
    """
    paths = _resolve_sources(raw_dir, ticket, limit)

    if not paths:
        typer.echo(f"BŁĄD: brak zgłoszeń do sparsowania w {raw_dir}", err=True)
        raise typer.Exit(code=2)

    settings = Settings()

    # Nadpisanie dociera do klienta tą samą drogą co wartość skonfigurowana — przez Settings — więc
    # fabryka zachowuje jedno źródło prawdy i fail-fast przy modelu bez cennika.
    if model is not None:
        settings = settings.model_copy(update={"llm_model": model})

    out_dir.mkdir(parents=True, exist_ok=True)

    # Atrapa offline nie ma nazwy modelu; „None" wyglądałoby tam na złą konfigurację.
    named_model = settings.llm_model or "(bez modelu)"

    typer.echo(f"Model: {named_model} ({settings.llm_provider})")
    typer.echo(f"Zgłoszeń do sparsowania: {len(paths)}\n")

    results = asyncio.run(_parse_all(TicketParser(get_llm_client(settings)), paths, out_dir))

    _print_parse_summary(results, out_dir)

    if any(not result.ok for result in results):
        raise typer.Exit(code=1)
