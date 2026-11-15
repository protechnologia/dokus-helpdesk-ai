"""Przygotowuje golden set zgłoszeń: parsuje go od nowa grafem `parse_ticket` albo zapisuje jego
wątki po anonimizacji obok kart.

Do czego:
    Pomiary filtra jakości i wyszukiwania stoją na kartach golden setu
    w `data/unsafe/golden/cards/`. Gdy zmienia się prompt parsujący, kontrakt karty albo model,
    te karty trzeba policzyć od nowa.
    Skrypt bierze numery zgłoszeń z golden setu (`data/unsafe/golden/tickets-vector.json`),
    czyta ich wątki z `data/unsafe/golden/raw-db/` i parsuje każdy tą samą drogą co trasa
    `/parse-ticket`: anonimizator, potem model generujący z `.env`. Karty idą do nowego katalogu
    roboczego, a katalog odniesienia zastępują dopiero wtedy, gdy człowiek je przyjmie.
    Wyszukiwanie w wątkach mierzy się na tabeli wątków golden setu, a tę `reindex` buduje
    z `anonymized/` obok kart. Komenda `anonymize` zapisuje tam wątki z tych samych surowych
    plików, z których powstały karty; `parse` ich nie zapisuje, bo nowe karty zastępują
    odniesienie dopiero po przyjęciu, a wątki zostają.

WYMAGA DZIAŁAJĄCEJ USŁUGI `anonymizer` Z MODELEM ANONIMIZUJĄCYM; `parse` TAKŻE PRAWDZIWEGO MODELU
GENERUJĄCEGO — KAŻDE ZGŁOSZENIE TO PŁATNE WYWOŁANIE:

    python scripts/parse_golden_tickets.py parse <nowy katalog kart>

    # cały zestaw, 4 naraz:
    python scripts/parse_golden_tickets.py parse data/unsafe/golden-gpt-6.1-sol-v3/cards

    # wątki po anonimizacji do data/unsafe/golden/anonymized/ (tylko anonimizator):
    python scripts/parse_golden_tickets.py anonymize

    # próba na dwóch zgłoszeniach: to samo z `--limit 2`

Przykład wyjścia (zmyślone liczby):

    Zgłoszeń: 200, już sparsowanych: 0, do zrobienia: 200 → data/unsafe/golden-gpt-6.1-sol-v3/cards
     10/200  błędów: 0  koszt: 0.0812 USD
     20/200  błędów: 1  koszt: 0.1655 USD
    …
    Gotowe: 199 kart, 1 błędów, koszt 1.6420 USD
    Błędy: 10544 (LLMError)

Co się dzieje po drodze:

1. Numery zgłoszeń to wpisy golden setu (`--golden`), a katalog kart odniesienia to jego
   `meta.corpus_dir`; do tego katalogu skrypt nie zapisuje. Katalog nad nim to korpus golden
   setu w układzie korpusu (`raw-db/`, `cards/`, `anonymized/`).
2. Zgłoszenie, którego karta już leży w katalogu wyjściowym, jest pomijane, więc przerwany
   przebieg wznawia się tym samym poleceniem.
3. Wątek z `raw-db/zgloszenie-<numer>.json` korpusu golden setu (lipcowy eksport) przechodzi
   przez graf `parse_ticket` na węzłach właściwych: anonimizacja, jedna tura modelu, walidacja
   karty.
4. Karta trafia na dysk od razu po sparsowaniu, a nie na końcu przebiegu.
5. Co dziesiąte zgłoszenie skrypt wypisuje postęp z sumą kosztu.

O czym pamiętać:

- Na wyjściu są wyłącznie numery, liczby i nazwy błędów, nigdy treść zgłoszeń: przebieg
  operuje na danych klientów.
- Katalog wyjściowy podaje się wprost, bez wartości domyślnej: nazwa katalogu roboczego mówi,
  którym modelem powstały karty, a model wybiera `.env`, więc domyślna nazwa w kodzie kłamałaby
  po jego zmianie.
- Przyjęte karty zastępują `data/unsafe/golden/cards/` ręcznie, po porównaniu pomiarów na obu
  katalogach; skrypt katalogu odniesienia nie rusza.
- Katalog wyjściowy to `cards/` w osobnym katalogu korpusu (np.
  `data/unsafe/golden-gpt-6.1-sol-v3/cards`), bo komendy `helpdesk tickets` biorą katalog
  korpusu: indeks do pomiaru buduje `QDRANT_COLLECTION=tickets_golden
  POSTGRES_TICKETS_TABLE=tickets_text_golden helpdesk tickets reindex
  data/unsafe/golden-gpt-6.1-sol-v3` (indeksy golden setu, osobne od instancji).
- Adres usługi `anonymizer` w `.env` to nazwa z sieci compose; z hosta skrypt woła ją pod
  `--anonymizer-url`.
- Błąd konfiguracji (model, klucz, anonimizator na atrapie silnika) zatrzymuje cały przebieg;
  błąd jednego zgłoszenia (model albo anonimizator chwilowo nie odpowiada, karta nie przeszła
  walidacji po poprawce) trafia do listy błędów, a przebieg idzie dalej.
"""

import asyncio
import json
import pathlib
import sys

import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.agent_graphs import parse_ticket  # noqa: E402  (po sys.path)
from app.agent_graphs.base import run_graph  # noqa: E402
from app.agent_graphs.factory import build_real_graph  # noqa: E402
from app.config import Settings  # noqa: E402
from app.core_model.tickets.tickets_corpus import TicketsCorpus  # noqa: E402
from app.core_service.loader_dict_resolution import get_resolution_classes  # noqa: E402
from app.core_service.parser_ticket_raw import load_raw_ticket  # noqa: E402
from app.engine_anonymization import (  # noqa: E402
    AnonymizationConfigError,
    AnonymizationError,
    Anonymizer,
    build_anonymizer,
)
from app.engine_llm import LLMConfigError, LLMError, get_llm_client  # noqa: E402

# Golden set zgłoszeń: wpis na każde zgłoszenie i w metryczce katalog kart odniesienia.
GOLDEN_DEFAULT = REPO_ROOT / "data" / "unsafe" / "golden" / "tickets-vector.json"

# Usługa `anonymizer` z hosta — zgodne z DOCKER_ANONYMIZER_PORT w `.env.example`.
ANONYMIZER_URL_DEFAULT = "http://localhost:8002"

# Ile zgłoszeń naraz. Anonimizator na jednym GPU i limity dostawcy modelu nie lubią większego
# ruchu, a 200 zgłoszeń po kilka sekund to i tak kilkanaście minut.
CONCURRENCY_DEFAULT = 4

# Co ile zgłoszeń wypisać postęp.
PROGRESS_EVERY = 10

cli = typer.Typer(help="Golden set zgłoszeń: ponowne parsowanie i wątki po anonimizacji.")


@cli.callback()
def main() -> None:
    """
    Description:
    Grupa komend skryptu: `parse` i `anonymize`.

    Example args:
        (brak)

    Example result:
        None
    """


def golden_tickets(
    golden: pathlib.Path,  # np. Path("data/unsafe/golden/tickets-vector.json")
) -> tuple[list[str], TicketsCorpus]:
    """
    Description:
    Czyta z pliku golden setu numery jego zgłoszeń, posortowane, i korpus golden setu: katalog
    nad katalogiem kart odniesienia z metryczki (`meta.corpus_dir`, ścieżka od korzenia repo).
    W nim leżą eksport (`raw-db/`), karty (`cards/`) i wątki po anonimizacji (`anonymized/`).

    Example args:
        golden=Path("data/unsafe/golden/tickets-vector.json")

    Example result:
        (["10012", "10170", …], TicketsCorpus(root=Path("/…/data/unsafe/golden")))
    """
    data      = json.loads(golden.read_text(encoding="utf-8"))
    ids       = sorted(entry["ticket_id"] for entry in data["tickets"])
    cards_dir = REPO_ROOT / data["meta"]["corpus_dir"]
    corpus    = TicketsCorpus(root=cards_dir.parent)

    return ids, corpus


def wanted_ids(
    all_ids:  list[str],  # np. ["10012", "10170"]
    done_ids: set[str],   # np. {"10012"} — numery plików, które już leżą w katalogu wyjściowym
    limit:    int | None, # np. 2 — próba na początku listy; None znaczy wszystkie
) -> tuple[list[str], int, int]:
    """
    Description:
    Wybiera numery zgłoszeń do zrobienia: wszystkie z golden setu bez tych, których plik już
    leży w katalogu wyjściowym. Oddaje też, ile zgłoszeń ma zestaw i ile z nich jest już
    zrobionych.

    Example args:
        all_ids=["10012", "10170", …]
        done_ids={"10012"}
        limit=None

    Example result:
        (["10170", …], 200, 1)
    """
    done    = done_ids & set(all_ids)
    todo    = [ticket_id for ticket_id in all_ids if ticket_id not in done]

    if limit is not None:
        todo = todo[:limit]

    return todo, len(all_ids), len(done)


async def parse_all(
    ticket_ids:     list[str],     # np. ["10012", "10170"]
    raw_dir:        pathlib.Path,  # np. Path("data/unsafe/golden/raw-db")
    out_dir:        pathlib.Path,  # np. Path("data/unsafe/golden-gpt-6.1-sol-v3/cards")
    anonymizer_url: str,           # np. "http://localhost:8002"
    concurrency:    int,           # np. 4
) -> tuple[int, list[tuple[str, str]], float]:
    """
    Description:
    Parsuje podane zgłoszenia po kilka naraz i zapisuje każdą kartę od razu. Oddaje liczbę
    zapisanych kart, listę błędów (numer i nazwa wyjątku) i łączny koszt w USD.

    Example args:
        ticket_ids=["10012", "10170"]
        raw_dir=Path("data/unsafe/golden/raw-db")
        out_dir=Path("data/unsafe/golden-gpt-6.1-sol-v3/cards")
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
    out_dir:        pathlib.Path = typer.Argument(help="Nowy katalog kart."),
    golden:         pathlib.Path = typer.Option(GOLDEN_DEFAULT, help="Golden set zgłoszeń."),
    anonymizer_url: str          = typer.Option(ANONYMIZER_URL_DEFAULT, help="Anonymizer z hosta."),
    concurrency:    int          = typer.Option(CONCURRENCY_DEFAULT, help="Ile zgłoszeń naraz."),
    limit:          int | None   = typer.Option(None, help="Tylko pierwsze N, na próbę."),
) -> None:
    """
    Description:
    Parsuje zgłoszenia golden setu z `raw-db/` jego korpusu do nowego katalogu kart, z postępem
    co 10 zgłoszeń i listą błędów na końcu. Kończy się kodem 1, gdy któreś zgłoszenie się nie
    udało.

    Example args:
        out_dir=Path("data/unsafe/golden-gpt-6.1-sol-v3/cards")
        golden=Path("data/unsafe/golden/tickets-vector.json")
        anonymizer_url="http://localhost:8002"
        concurrency=4
        limit=None

    Example result:
        None — karty w `out_dir`, podsumowanie na wyjściu

    Raises:
        typer.Exit: code 1, gdy któreś zgłoszenie skończyło się błędem; code 2, gdy katalog
            wyjściowy to katalog kart odniesienia
    """
    all_ids, corpus = golden_tickets(golden)

    # Na kartach odniesienia stoją pomiary, a zastępuje się je dopiero po przyjęciu nowych:
    # wyjście w tym katalogu nadpisałoby je bez porównania.
    if out_dir.resolve() == corpus.cards_dir.resolve():
        typer.echo("BŁĄD: katalog wyjściowy to katalog kart odniesienia — nadpisałby je.", err=True)
        raise typer.Exit(code=2)

    parsed            = {path.stem for path in out_dir.glob("*.json")}
    todo, total, done = wanted_ids(all_ids, parsed, limit)

    typer.echo(
        f"Zgłoszeń: {total}, już sparsowanych: {done}, do zrobienia: {len(todo)} → {out_dir}"
    )

    run                 = parse_all(todo, corpus.raw_db_dir, out_dir, anonymizer_url, concurrency)
    saved, errors, cost = asyncio.run(run)

    typer.echo(f"Gotowe: {saved} kart, {len(errors)} błędów, koszt {cost:.4f} USD")

    if errors:
        typer.echo("Błędy: " + ", ".join(f"{ticket_id} ({name})" for ticket_id, name in errors))
        raise typer.Exit(code=1)


async def anonymize_all(
    ticket_ids:  list[str],      # np. ["10012", "10170"]
    corpus:      TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/golden"))
    anonymizer:  Anonymizer,     # np. AnonymizerClient(…) usługi `anonymizer` z hosta
    concurrency: int,            # np. 4
) -> tuple[int, list[tuple[str, str]]]:
    """
    Description:
    Anonimizuje wątki podanych zgłoszeń z `raw-db/` korpusu po kilka naraz i zapisuje każdy od
    razu do `anonymized/<numer>.txt` tego korpusu, w kształcie z masowego importu: wątek
    z `as_thread()` po anonimizacji. Oddaje liczbę zapisanych wątków i listę błędów (numer
    i nazwa wyjątku).

    Example args:
        ticket_ids=["10012", "10170"]
        corpus=TicketsCorpus(root=Path("data/unsafe/golden"))
        anonymizer=AnonymizerClient(…)
        concurrency=4

    Example result:
        (2, [])

    Raises:
        AnonymizationConfigError: anonimizator odmówił z powodu konfiguracji
    """
    corpus.anonymized_dir.mkdir(parents=True, exist_ok=True)

    gate   = asyncio.Semaphore(concurrency)
    errors: list[tuple[str, str]] = []
    totals = {"done": 0, "saved": 0}

    async def one(
        ticket_id: str,  # np. "10012"
    ) -> None:
        """
        Description:
        Anonimizuje wątek jednego zgłoszenia i zapisuje go; błąd zgłoszenia dopisuje do listy
        błędów. Co dziesiąte zakończone zgłoszenie wypisuje postęp.

        Example args:
            ticket_id="10012"

        Example result:
            None — wątek w `anonymized/10012.txt`
        """
        async with gate:
            raw = load_raw_ticket(corpus.raw_db_dir / f"zgloszenie-{ticket_id}.json")

            try:
                thread = await anonymizer.anonymize(raw.as_thread())
            # --- konfiguracja: czekanie nic nie da, cały przebieg staje ---
            except AnonymizationConfigError:
                raise
            # --- jedno zgłoszenie: zapisujemy nazwę błędu, bez treści, i idziemy dalej ---
            except AnonymizationError as exc:
                errors.append((ticket_id, type(exc).__name__))
            else:
                path = corpus.anonymized_dir / f"{ticket_id}.txt"

                path.write_text(thread.text, encoding="utf-8")

                totals["saved"] += 1

            totals["done"] += 1

            if totals["done"] % PROGRESS_EVERY == 0 or totals["done"] == len(ticket_ids):
                typer.echo(f"{totals['done']:>4}/{len(ticket_ids)}  błędów: {len(errors)}")

    await asyncio.gather(*(one(ticket_id) for ticket_id in ticket_ids))

    return totals["saved"], errors


async def _anonymize_with_service(
    ticket_ids:     list[str],      # np. ["10012", "10170"]
    corpus:         TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/golden"))
    anonymizer_url: str,            # np. "http://localhost:8002"
    concurrency:    int,            # np. 4
) -> tuple[int, list[tuple[str, str]]]:
    """
    Description:
    Buduje klienta usługi `anonymizer` z hosta, anonimizuje nim wątki i zamyka go także po
    błędzie w połowie przebiegu.

    Example args:
        ticket_ids=["10012", "10170"]
        corpus=TicketsCorpus(root=Path("data/unsafe/golden"))
        anonymizer_url="http://localhost:8002"
        concurrency=4

    Example result:
        (2, [])

    Raises:
        AnonymizationConfigError: model generujący to atrapa albo usługa ma atrapę silnika
    """
    settings = Settings(anonymization_base_url=anonymizer_url)

    # Przy atrapie modelu generującego klient przyjmuje wynik atrapy silnika, która oddaje tekst
    # bez zmian: do `anonymized/` trafiłby wtedy surowy wątek z danymi osobowymi.
    if settings.llm_generation().provider.strip().lower() == "fake":
        raise AnonymizationConfigError(
            "LLM_GENERATION_PROVIDER=fake — klient przyjąłby tekst z atrapy silnika bez zmian"
        )

    anonymizer = build_anonymizer(settings)

    try:
        return await anonymize_all(ticket_ids, corpus, anonymizer, concurrency)
    finally:
        await anonymizer.aclose()


@cli.command("anonymize", help="Zapisuje wątki golden setu po anonimizacji obok jego kart.")
def anonymize(
    golden:         pathlib.Path = typer.Option(GOLDEN_DEFAULT, help="Golden set zgłoszeń."),
    anonymizer_url: str          = typer.Option(ANONYMIZER_URL_DEFAULT, help="Anonymizer z hosta."),
    concurrency:    int          = typer.Option(CONCURRENCY_DEFAULT, help="Ile zgłoszeń naraz."),
    limit:          int | None   = typer.Option(None, help="Tylko pierwsze N, na próbę."),
) -> None:
    """
    Description:
    Anonimizuje wątki zgłoszeń golden setu z `raw-db/` do `anonymized/` jego korpusu,
    z postępem co 10 zgłoszeń i listą błędów na końcu. Zgłoszenie, którego wątek już leży,
    pomija, więc przerwany przebieg wznawia się tym samym poleceniem. Kart nie rusza. Kończy się
    kodem 1, gdy któreś zgłoszenie się nie udało, a kodem 2 przy błędzie konfiguracji.

    Example args:
        golden=Path("data/unsafe/golden/tickets-vector.json")
        anonymizer_url="http://localhost:8002"
        concurrency=4
        limit=None

    Example result:
        None — wątki w `data/unsafe/golden/anonymized/`, podsumowanie na wyjściu

    Raises:
        typer.Exit: code 1, gdy któreś zgłoszenie skończyło się błędem; code 2 przy błędzie
            konfiguracji anonimizatora
    """
    # Korpus wynika z metryczki golden setu, więc wątkami nie da się przez pomyłkę dopisać do
    # korpusu instancji.
    all_ids, corpus   = golden_tickets(golden)
    written           = {path.stem for path in corpus.anonymized_dir.glob("*.txt")}
    todo, total, done = wanted_ids(all_ids, written, limit)

    typer.echo(
        f"Zgłoszeń: {total}, już z wątkiem: {done}, do zrobienia: {len(todo)} → "
        f"{corpus.anonymized_dir}"
    )

    try:
        run           = _anonymize_with_service(todo, corpus, anonymizer_url, concurrency)
        saved, errors = asyncio.run(run)
    except AnonymizationConfigError as exc:
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Gotowe: {saved} wątków, {len(errors)} błędów")

    if errors:
        typer.echo("Błędy: " + ", ".join(f"{ticket_id} ({name})" for ticket_id, name in errors))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    cli()
