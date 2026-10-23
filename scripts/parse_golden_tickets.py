"""Parsuje od nowa zgłoszenia golden setu grafem `parse_ticket` i zapisuje karty do nowego katalogu.

Do czego:
    Karty w `data/unsafe/parsed/bielik-11b-golden200/` powstały starszym promptem i nie mają pól
    dodanych później do kontraktu (`excluded_causes`, `useful`, `useful_reason`), więc nowy
    `ParsedTicket` ich nie przyjmuje. Ten skrypt bierze numery zgłoszeń z tamtego katalogu, czyta
    ich wątki z `data/unsafe/raw/` i parsuje każdy tą samą drogą co trasa `/parse-ticket`:
    anonimizator, potem model generujący z `.env`. Stary katalog zostaje nietknięty (zasada 7).

WYMAGA DZIAŁAJĄCEJ USŁUGI `anonymizer` Z MODELEM ANONIMIZUJĄCYM I PRAWDZIWEGO MODELU
GENERUJĄCEGO — KAŻDE ZGŁOSZENIE TO PŁATNE WYWOŁANIE:

    python scripts/parse_golden_tickets.py parse <karty wzorcowe> <nowy katalog kart>

    # cały zestaw, 4 naraz:
    python scripts/parse_golden_tickets.py parse data/unsafe/parsed/bielik-11b-golden200 \
        data/unsafe/parsed/gpt-6.1-sol-golden200

    # próba na dwóch zgłoszeniach: to samo z `--limit 2`

Przykład wyjścia (zmyślone liczby):

    Zgłoszeń: 200, już sparsowanych: 0, do zrobienia: 200 → data/unsafe/parsed/gpt-6.1-sol-golden200
     10/200  błędów: 0  koszt: 0.0812 USD
     20/200  błędów: 1  koszt: 0.1655 USD
    …
    Gotowe: 199 kart, 1 błędów, koszt 1.6420 USD
    Błędy: 10544 (LLMError)

Co się dzieje po drodze:

1. Numery zgłoszeń to nazwy plików z katalogu wzorcowego (pierwszy argument).
2. Zgłoszenie, którego karta już leży w katalogu wyjściowym, jest pomijane, więc przerwany
   przebieg wznawia się tym samym poleceniem.
3. Wątek z `data/unsafe/raw/zgloszenie-<numer>.json` przechodzi przez graf `parse_ticket` na
   węzłach właściwych: anonimizacja, jedna tura modelu, walidacja karty.
4. Karta trafia na dysk od razu po sparsowaniu, a nie na końcu przebiegu.
5. Co dziesiąte zgłoszenie skrypt wypisuje postęp z sumą kosztu.

O czym pamiętać:

- Na wyjściu są wyłącznie numery, liczby i nazwy błędów, nigdy treść zgłoszeń: przebieg
  operuje na danych klientów.
- Oba katalogi podaje się wprost, bez wartości domyślnych: nazwa katalogu kart mówi, którym
  modelem powstały, a model wybiera `.env`, więc domyślna nazwa w kodzie kłamałaby po jego
  zmianie.
- Adres usługi `anonymizer` w `.env` to nazwa z sieci compose; z hosta skrypt woła ją pod
  `--anonymizer-url`.
- Błąd konfiguracji (model, klucz, anonimizator na atrapie silnika) zatrzymuje cały przebieg;
  błąd jednego zgłoszenia (model albo anonimizator chwilowo nie odpowiada, karta nie przeszła
  walidacji po poprawce) trafia do listy błędów, a przebieg idzie dalej.
"""

import asyncio
import pathlib
import sys

import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.agent_graphs import parse_ticket  # noqa: E402  (po sys.path)
from app.agent_graphs.base import run_graph  # noqa: E402
from app.agent_graphs.factory import build_real_graph  # noqa: E402
from app.config import Settings  # noqa: E402
from app.core_service.loader_dict_resolution import get_resolution_classes  # noqa: E402
from app.core_service.parser_ticket_raw import load_raw_ticket  # noqa: E402
from app.engine_anonymization import (  # noqa: E402
    AnonymizationConfigError,
    AnonymizationError,
    build_anonymizer,
)
from app.engine_llm import LLMConfigError, LLMError, get_llm_client  # noqa: E402

# Wątki zgłoszeń, tak jak zdjął je `export_raw_tickets.py`.
RAW_DIR_DEFAULT = REPO_ROOT / "data" / "unsafe" / "raw"

# Usługa `anonymizer` z hosta — zgodne z DOCKER_ANONYMIZER_PORT w `.env.example`.
ANONYMIZER_URL_DEFAULT = "http://localhost:8002"

# Ile zgłoszeń naraz. Anonimizator na jednym GPU i limity dostawcy modelu nie lubią większego
# ruchu, a 200 zgłoszeń po kilka sekund to i tak kilkanaście minut.
CONCURRENCY_DEFAULT = 4

# Co ile zgłoszeń wypisać postęp.
PROGRESS_EVERY = 10

cli = typer.Typer(help="Ponowne parsowanie golden setu grafem parse_ticket.")


@cli.callback()
def main() -> None:
    """
    Description:
    Grupa komend skryptu. Callback zostawia drzewo subkomend, choć komenda jest jedna — inaczej
    Typer uruchomiłby ją bez nazwy.

    Example args:
        (brak)

    Example result:
        None
    """


def wanted_ids(
    ids_from: pathlib.Path,  # np. Path("data/unsafe/parsed/bielik-11b-golden200")
    out_dir:  pathlib.Path,  # np. Path("data/unsafe/parsed/gpt-6.1-sol-golden200")
    limit:    int | None,    # np. 2 — próba na początku listy; None znaczy wszystkie
) -> tuple[list[str], int, int]:
    """
    Description:
    Numery zgłoszeń do sparsowania: nazwy plików katalogu wzorcowego, posortowane, bez tych,
    których karta już leży w katalogu wyjściowym. Oddaje też, ile zgłoszeń ma zestaw i ile
    z nich jest już sparsowanych.

    Example args:
        ids_from=Path("data/unsafe/parsed/bielik-11b-golden200")
        out_dir=Path("data/unsafe/parsed/gpt-6.1-sol-golden200")
        limit=None

    Example result:
        (["10012", "10170", …], 200, 0)
    """
    all_ids = sorted(path.stem for path in ids_from.glob("*.json"))
    done    = {path.stem for path in out_dir.glob("*.json")} & set(all_ids)
    todo    = [ticket_id for ticket_id in all_ids if ticket_id not in done]

    if limit is not None:
        todo = todo[:limit]

    return todo, len(all_ids), len(done)


async def parse_all(
    ticket_ids:     list[str],     # np. ["10012", "10170"]
    raw_dir:        pathlib.Path,  # np. Path("data/unsafe/raw")
    out_dir:        pathlib.Path,  # np. Path("data/unsafe/parsed/gpt-6.1-sol-golden200")
    anonymizer_url: str,           # np. "http://localhost:8002"
    concurrency:    int,           # np. 4
) -> tuple[int, list[tuple[str, str]], float]:
    """
    Description:
    Parsuje podane zgłoszenia po kilka naraz i zapisuje każdą kartę od razu. Oddaje liczbę
    zapisanych kart, listę błędów (numer i nazwa wyjątku) i łączny koszt w USD.

    Example args:
        ticket_ids=["10012", "10170"]
        raw_dir=Path("data/unsafe/raw")
        out_dir=Path("data/unsafe/parsed/gpt-6.1-sol-golden200")
        anonymizer_url="http://localhost:8002"
        concurrency=4

    Example result:
        (2, [], 0.0164)

    Raises:
        LLMConfigError: model generujący jest źle skonfigurowany albo to atrapa
        AnonymizationConfigError: anonimizator odmówił z powodu konfiguracji
    """
    # --- zależności grafu: te same, z których fabryka składa trasę ---
    settings = Settings(anonymization_base_url=anonymizer_url)

    if settings.llm_generation().provider.strip().lower() == "fake":
        raise LLMConfigError("LLM_GENERATION_PROVIDER=fake — atrapa modelu nie parsuje kart")

    anonymizer = build_anonymizer(settings)
    graph      = build_real_graph(
        graph          = parse_ticket,
        llm            = get_llm_client(settings.llm_generation()),
        anonymizer     = anonymizer,
        tools          = [],
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )
    vocabulary = get_resolution_classes()

    out_dir.mkdir(parents=True, exist_ok=True)

    gate   = asyncio.Semaphore(concurrency)
    errors: list[tuple[str, str]] = []
    totals = {"done": 0, "saved": 0, "cost": 0.0}

    async def one(
        ticket_id: str,  # np. "10012"
    ) -> None:
        """
        Description:
        Parsuje jedno zgłoszenie i zapisuje jego kartę; błąd zgłoszenia dopisuje do listy błędów.
        Co dziesiąte zakończone zgłoszenie wypisuje postęp.

        Example args:
            ticket_id="10012"

        Example result:
            None — karta w `out_dir/10012.json`
        """
        async with gate:
            raw   = load_raw_ticket(raw_dir / f"zgloszenie-{ticket_id}.json")
            state = parse_ticket.STATE(
                input_text = raw.as_thread(),
                ticket_id  = raw.ticket_id,
                date       = raw.date,
                vocabulary = vocabulary,
            )

            try:
                final = await run_graph(graph, state)
            # --- konfiguracja: czekanie nic nie da, cały przebieg staje ---
            except (LLMConfigError, AnonymizationConfigError):
                raise
            # --- jedno zgłoszenie: zapisujemy nazwę błędu, bez treści, i idziemy dalej ---
            except (LLMError, AnonymizationError) as exc:
                errors.append((ticket_id, type(exc).__name__))
            else:
                card_path = out_dir / f"{ticket_id}.json"
                card_json = final.output.model_dump_json(indent=2)

                card_path.write_text(card_json + "\n", encoding="utf-8")

                totals["saved"] += 1
                totals["cost"]  += final.usage.cost_usd

            totals["done"] += 1

            if totals["done"] % PROGRESS_EVERY == 0 or totals["done"] == len(ticket_ids):
                typer.echo(
                    f"{totals['done']:>4}/{len(ticket_ids)}  błędów: {len(errors)}  "
                    f"koszt: {totals['cost']:.4f} USD"
                )

    try:
        await asyncio.gather(*(one(ticket_id) for ticket_id in ticket_ids))
    finally:
        await anonymizer.aclose()

    return totals["saved"], errors, totals["cost"]


@cli.command("parse", help="Parsuje golden set od nowa do nowego katalogu kart.")
def parse(
    ids_from:       pathlib.Path = typer.Argument(help="Karty, z których brać numery."),
    out_dir:        pathlib.Path = typer.Argument(help="Nowy katalog kart."),
    raw_dir:        pathlib.Path = typer.Option(RAW_DIR_DEFAULT, help="Wątki zgłoszeń."),
    anonymizer_url: str          = typer.Option(ANONYMIZER_URL_DEFAULT, help="Anonymizer z hosta."),
    concurrency:    int          = typer.Option(CONCURRENCY_DEFAULT, help="Ile zgłoszeń naraz."),
    limit:          int | None   = typer.Option(None, help="Tylko pierwsze N, na próbę."),
) -> None:
    """
    Description:
    Parsuje zgłoszenia golden setu do nowego katalogu kart, z postępem co 10 zgłoszeń i listą
    błędów na końcu. Kończy się kodem 1, gdy któreś zgłoszenie się nie udało.

    Example args:
        ids_from=Path("data/unsafe/parsed/bielik-11b-golden200")
        out_dir=Path("data/unsafe/parsed/gpt-6.1-sol-golden200")
        raw_dir=Path("data/unsafe/raw")
        anonymizer_url="http://localhost:8002"
        concurrency=4
        limit=None

    Example result:
        None — karty w `out_dir`, podsumowanie na wyjściu

    Raises:
        typer.Exit: code 1, gdy któreś zgłoszenie skończyło się błędem
    """
    # Katalog wzorcowy jest niepowtarzalnym artefaktem: wyjście w nim nadpisałoby karty.
    if out_dir.resolve() == ids_from.resolve():
        typer.echo("BŁĄD: katalog wyjściowy to katalog wzorcowy — karty by nadpisał.", err=True)
        raise typer.Exit(code=2)

    todo, total, done = wanted_ids(ids_from, out_dir, limit)

    typer.echo(
        f"Zgłoszeń: {total}, już sparsowanych: {done}, do zrobienia: {len(todo)} → {out_dir}"
    )

    run                 = parse_all(todo, raw_dir, out_dir, anonymizer_url, concurrency)
    saved, errors, cost = asyncio.run(run)

    typer.echo(f"Gotowe: {saved} kart, {len(errors)} błędów, koszt {cost:.4f} USD")

    if errors:
        typer.echo("Błędy: " + ", ".join(f"{ticket_id} ({name})" for ticket_id, name in errors))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    cli()
