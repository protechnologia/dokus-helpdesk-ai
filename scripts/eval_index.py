"""Measure recall@K of the BUILT index — through Qdrant and the embedder service, not in memory.

OBIE KOMENDY WYMAGAJĄ ZBUDOWANEGO INDEKSU I CHODZĄCEGO STACKU:

    docker compose up -d                          # embedder + qdrant
    helpdesk rag index data/parsed/<zestaw>       # napełnij kolekcję
    python scripts/eval_index.py recall           # recall@K jednego trybu
    python scripts/eval_index.py modes            # porównanie query→passage z sts→sts

Bez kolekcji obie kończą się kodem 2 i mówią, czego brakuje — zamiast drukować raport zer, bo
0% wyglądałoby jak problem modelu, a byłoby brakiem danych.

Do czego:
    Sprawdza OKABLOWANIE, nie jakość modelu. Etap 3 policzył recall@1 = 98,2% ładując model
    wprost i licząc podobieństwa w numpy; tutaj to samo zapytanie przechodzi przez usługę
    `embedder`, kolekcję Qdranta i named vectory zbudowane przez `helpdesk rag index`. Zgodny
    wynik znaczy, że po drodze nic się nie pomyliło; rozjazd wskazuje, GDZIE (CLAUDE.md → 4.4).

    **Tej liczby nie wolno czytać jako skuteczności produktu.** Golden set powstał z tych samych
    200 rekordów, które są w indeksie, więc każde zapytanie ma tam swój cel — w produkcji tak
    nie będzie.

Co ten pomiar potrafi złapać, a czego pomiar z etapu 3 nie potrafił:
    - **pomylone tryby prefiksów** — zapytanie embedowane jako `passage` albo szukanie po
      wektorze `sts` zamiast `problem`; wektory dalej wyglądają poprawnie, tylko trafienia są złe,
    - **rozjazd tekstu** — gdyby indeksacja i zapytanie budowały `embedding_text()` inaczej,
    - **rekordy zgubione przez filtr albo upsert** — zapytanie do rekordu, którego w indeksie nie
      ma, wychodzi tu jako brak trafienia, a nie jako niższa ranga.

Flow (`recall`; `modes` powtarza kroki 2-4 dla obu par tryb↔wektor):
    1. Wczytuje golden set i pyta Qdranta o rozmiar kolekcji.
    2. Embeduje zapytania przez usługę `embedder` w trybie `query` (partiami).
    3. Szuka każdego wektora w kolekcji po named vectorze `problem`, biorąc top-K.
    4. Liczy krzywą recall@1..K i MRR — tymi samymi wzorami co `eval_embeddings.py`.

Adresy usług są argumentami (`--embedder`, `--qdrant`) i domyślnie wskazują **porty hosta**
publikowane przez compose, nie nazwy z sieci compose: skrypt jest repo-level i chodzi obok stacku.
"""

import json
import pathlib
import sys

import httpx
import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# `app` mieszka w api/ i nie jest na ścieżce przy uruchomieniu `python scripts/...`.
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.retrieval.model_point import VECTOR_PROBLEM, VECTOR_STS  # noqa: E402  (po sys.path)

DEFAULT_GOLDEN = REPO_ROOT / "data" / "golden" / "bielik-11b-golden200.json"

# Adresy z HOSTA, nie z sieci compose: skrypt jest repo-level i chodzi obok stacku, więc widzi
# usługi przez opublikowane porty, a nie po nazwach kontenerów.
DEFAULT_EMBEDDER = "http://localhost:8001"
DEFAULT_QDRANT   = "http://localhost:6333"

# Ile zapytań idzie w jednym wywołaniu embeddera. Tyle samo co przy indeksacji — wielkość partii
# nie ma prawa zmieniać wektora, a jeśli zmienia, to jest to defekt wart wykrycia.
EMBED_BATCH_SIZE = 32

# Ranga przypisywana zapytaniu, którego rekord nie wrócił w top-K. Wpada poza każde `recall@K`
# i wnosi ~0 do MRR — czyli zachowuje się jak „bardzo daleko", zamiast wywracać przebieg.
RANK_NOT_FOUND = 10**6

cli = typer.Typer(help="Pomiar recall@K na zbudowanym indeksie Qdranta.")

HELP_COMMAND = "Liczy recall@K przez usługę embeddera i Qdranta, na zbudowanej kolekcji."
HELP_MODES   = "Porównuje query→passage z sts→sts na zapytaniach surowych i sparsowanych."


def _load_queries(
    golden_path: pathlib.Path,  # e.g. Path("data/golden/bielik-11b-golden200.json")
) -> list[dict]:
    """
    Description:
    Reads the golden set queries. Only `queries` matter here — `rejected` records are deliberately
    left in the index as distractors, so they need no entry of their own.

    Example args:
        golden_path=Path("data/golden/bielik-11b-golden200.json")

    Example result:
        [{"expected_ticket_id": 5641, "query_raw": "Dzień dobry, nie mogę…", …}]
    """
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    return golden["queries"]


def _embed_queries(
    client: httpx.Client,  # e.g. httpx.Client(base_url="http://localhost:8001")
    texts:  list[str],     # e.g. ["Dzień dobry, nie mogę podpisać pisma…"]
    mode:   str = "query", # e.g. "sts" — must match the named vector searched afterwards
) -> list[list[float]]:
    """
    Description:
    Embeds every query through the running `embedder`, in the given mode and in batches.

    Mode matters more than anything else here: `[query]:` results may only be searched against
    `passage` vectors and `[sts]:` only against `sts` ones, because mixing the two destroys
    retrieval while every vector still looks valid (CLAUDE.md → "Embeddingi"). It is a parameter
    only so the `modes` command can compare the two PAIRS — never to mix the halves.

    Sending them through the SERVICE rather than loading the model is the whole point: that is the
    path production takes.

    Example args:
        client=httpx.Client(base_url="http://localhost:8001")
        texts=["Dzień dobry, nie mogę podpisać pisma…"]
        mode="query"

    Example result:
        [[0.0123, -0.0456, …]]
    """
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]

        try:
            response = client.post("/embed", json={"texts": batch, "mode": mode})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Same reasoning as in `_collection_size`: a stack that is not up must produce a
            # sentence, not a traceback from inside httpx.
            typer.echo(
                f"BŁĄD: nie ma kontaktu z embedderem ({client.base_url}): {exc}\n"
                f"       Podnieś stack: `docker compose up -d`.",
                err=True,
            )
            raise typer.Exit(code=2) from exc

        vectors.extend(response.json()["vectors"])

    return vectors


def _search_ranks(
    client:       httpx.Client,       # e.g. httpx.Client(base_url="http://localhost:6333")
    collection:   str,                # e.g. "tickets"
    vectors:      list[list[float]],  # e.g. [[0.0123, -0.0456, …]]
    expected_ids: list[str],          # e.g. ["5641", "5656"] — one per query, in order
    k_max:        int,                # e.g. 5
    vector_name:  str = VECTOR_PROBLEM,  # e.g. "sts" — must match the mode used to embed
) -> list[int]:
    """
    Description:
    Searches each query vector in the collection and returns the 1-based position of its expected
    record, or `RANK_NOT_FOUND` when it did not come back at all.

    Unlike the in-memory measurement of stage 3, Qdrant returns only top-K — so "not in the
    results" is a THIRD outcome next to "first" and "fifth", and it has to be counted as a miss
    rather than silently skipped. That distinction is what makes this run able to catch a record
    dropped by the filter or lost during upsert.

    Example args:
        client=httpx.Client(base_url="http://localhost:6333")
        collection="tickets"
        vectors=[[0.0123, -0.0456]]
        expected_ids=["5641"]
        k_max=5

    Example result:
        [1]
    """
    ranks = []

    for vector, expected in zip(vectors, expected_ids, strict=True):
        response = client.post(
            f"/collections/{collection}/points/search",
            json={
                # Named vector, spelled explicitly: the collection holds two, and searching the
                # wrong one returns plausible-looking nonsense rather than an error.
                "vector":       {"name": vector_name, "vector": vector},
                "limit":        k_max,
                "with_payload": True,
            },
        )
        response.raise_for_status()

        hits = response.json()["result"]
        # Payload carries `ticket_id`; the point id is a UUID derived from it, so matching on the
        # payload keeps this readable and independent of how ids are derived.
        found = [str(hit["payload"]["ticket_id"]) for hit in hits]

        ranks.append(found.index(expected) + 1 if expected in found else RANK_NOT_FOUND)

    return ranks


def _collection_size(
    client:     httpx.Client,  # e.g. httpx.Client(base_url="http://localhost:6333")
    collection: str,           # e.g. "tickets"
) -> int:
    """
    Description:
    Returns how many points the collection holds, refusing to go on when there is nothing to
    measure. Every failure exits 2 rather than producing a report of zeros — a run against a
    missing or empty index would otherwise print a perfectly formatted 0% and look like a model
    problem.

    Also the place where an unreachable Qdrant is caught: this is the FIRST call the script makes,
    so a stack that is not up stops here with a sentence instead of a traceback from inside httpx.

    Example args:
        client=httpx.Client(base_url="http://localhost:6333")
        collection="tickets"

    Example result:
        171

    Raises:
        typer.Exit: code 2 when Qdrant is unreachable, or the collection is missing or empty
    """
    try:
        info = client.get(f"/collections/{collection}")
    except httpx.HTTPError as exc:
        typer.echo(
            f"BŁĄD: nie ma kontaktu z Qdrantem ({client.base_url}): {exc}\n"
            f"       Podnieś stack: `docker compose up -d`.",
            err=True,
        )
        raise typer.Exit(code=2) from exc

    if info.status_code == 404:
        typer.echo(
            f"BŁĄD: nie ma kolekcji '{collection}' — zbuduj ją `helpdesk rag index`.", err=True
        )
        raise typer.Exit(code=2)

    count  = client.post(f"/collections/{collection}/points/count", json={"exact": True})
    points = count.json()["result"]["count"]

    if points == 0:
        typer.echo(f"BŁĄD: kolekcja '{collection}' jest pusta.", err=True)
        raise typer.Exit(code=2)

    return points


def _metrics(
    ranks: list[int],  # e.g. [1, 3, 7]
    k_max: int = 5,
) -> tuple[list[float], float]:
    """
    Description:
    Turns ranks into the recall curve (recall@1 … recall@k_max) plus MRR.

    Same formulas as `eval_embeddings.py` on purpose — the two numbers are meant to be compared,
    and a second definition of recall would make the comparison meaningless.

    Example args:
        ranks=[1, 3, 7]
        k_max=5

    Example result:
        ([33.3, 33.3, 66.7, 66.7, 66.7], 0.48)
    """
    total = len(ranks)

    if not total:
        return [0.0] * k_max, 0.0

    curve = [100 * sum(1 for r in ranks if r <= k) / total for k in range(1, k_max + 1)]
    mrr   = sum(1 / r for r in ranks) / total

    return curve, mrr


def _report(
    ranks:      list[int],   # e.g. [1, 1, 3]
    queries:    list[dict],  # e.g. [{"kind": "eksploatacyjne", "difficulty": "typowe"}]
    k_max:      int,         # e.g. 5
    collection: str,         # e.g. "tickets"
    points:     int,         # e.g. 171
) -> None:
    """
    Description:
    Prints the curve and MRR overall, then split by query kind and difficulty, plus the misses.

    Misses are listed by ticket id rather than counted: at this scale each one is a concrete
    record to look at, and "which ones" is the question that follows any number below 100%.

    Example args:
        ranks=[1, 1, 3]
        queries=[{"kind": "eksploatacyjne", "difficulty": "typowe"}, …]
        k_max=5
        collection="tickets"
        points=171

    Example result:
        None — writes the report to stdout
    """
    def line(name: str, subset: list[int]) -> str:
        curve, mrr = _metrics(subset, k_max)
        cells      = "  ".join(f"@{k}:{value:5.1f}" for k, value in enumerate(curve, start=1))

        return f"    {name:<26} {cells}   MRR {mrr:.3f}  (n={len(subset)})"

    typer.echo(f"\nKolekcja '{collection}': {points} punktów, {len(ranks)} zapytań\n")
    typer.echo(line("RAZEM", ranks))

    # --- per warstwa golden setu ---
    for field in ("kind", "difficulty"):
        values = sorted({query.get(field, "?") for query in queries})

        if len(values) < 2:
            continue

        typer.echo("")

        for value in values:
            subset = [
                rank
                for rank, query in zip(ranks, queries, strict=True)
                if query.get(field) == value
            ]

            if subset:
                typer.echo(line(value, subset))

    # --- czego nie znaleziono wcale ---
    missed = [
        str(query["expected_ticket_id"])
        for rank, query in zip(ranks, queries, strict=True)
        if rank == RANK_NOT_FOUND
    ]

    if missed:
        typer.echo(f"\nPoza top-{k_max} ({len(missed)}): {', '.join(missed)}")


@cli.callback()
def main() -> None:
    """
    Description:
    Root callback. Keeps Typer in subcommand mode even with a single command, so the script grows
    a second measurement without changing how the first one is invoked.

    Example args:
        (none)

    Example result:
        None
    """


@cli.command("recall", help=HELP_COMMAND)
def recall(
    collection: str  = typer.Option("tickets", help="Kolekcja Qdranta do przeszukania."),
    golden:     pathlib.Path = typer.Option(DEFAULT_GOLDEN, help="Plik golden setu."),
    embedder:   str  = typer.Option(DEFAULT_EMBEDDER, help="Adres usługi embeddera."),
    qdrant:     str  = typer.Option(DEFAULT_QDRANT, help="Adres Qdranta."),
    k_max:      int  = typer.Option(5, help="Największe K w krzywej recall@K."),
) -> None:
    """
    Description:
    Runs the measurement against a built collection and prints the report.

    Example args:
        collection="tickets"
        k_max=5

    Example result:
        prints the recall curve, MRR and the list of misses

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    queries = _load_queries(golden)

    with httpx.Client(base_url=qdrant, timeout=30.0) as qdrant_client:
        points = _collection_size(qdrant_client, collection)

        # --- zapytania przez usługę, nie przez wagi modelu ---
        with httpx.Client(base_url=embedder, timeout=120.0) as embedder_client:
            vectors = _embed_queries(embedder_client, [q["query_raw"] for q in queries])

        ranks = _search_ranks(
            client       = qdrant_client,
            collection   = collection,
            vectors      = vectors,
            expected_ids = [str(q["expected_ticket_id"]) for q in queries],
            k_max        = k_max,
        )

    _report(ranks, queries, k_max, collection, points)


@cli.command("modes", help=HELP_MODES)
def modes(
    collection: str  = typer.Option("tickets", help="Kolekcja Qdranta do przeszukania."),
    golden:     pathlib.Path = typer.Option(DEFAULT_GOLDEN, help="Plik golden setu."),
    embedder:   str  = typer.Option(DEFAULT_EMBEDDER, help="Adres usługi embeddera."),
    qdrant:     str  = typer.Option(DEFAULT_QDRANT, help="Adres Qdranta."),
    k_max:      int  = typer.Option(5, help="Największe K w krzywej recall@K."),
) -> None:
    """
    Description:
    Compares the two search modes on RAW and on PARSED-style queries — four measurements, one
    table. Settles the axis stage 3 left open: whether `sts→sts` overtakes `query→passage` once
    both sides of the comparison are the same kind of text.

    The four rows are two PAIRS, never four free combinations: `[query]:` may only be searched
    against `passage` vectors and `[sts]:` only against `sts` ones. Mixing the halves measures our
    own mistake, not the modes (CLAUDE.md → "Embeddingi").

    Example args:
        collection="tickets"
        k_max=5

    Example result:
        prints a four-row table plus the difference between the two modes per input kind

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    queries  = _load_queries(golden)
    expected = [str(query["expected_ticket_id"]) for query in queries]

    # Two kinds of query text. `expected_problem` stands in for a PARSED query — it is a copy of
    # the target record's `problem`, so it is the right KIND of text (short, factual, no greeting)
    # without needing an LLM pass. It comes from the target itself, so absolute figures are
    # optimistic for BOTH modes; the difference between them is what this table is for.
    inputs = {
        "SUROWE":     [query["query_raw"] for query in queries],
        "SPARSOWANE": [query["expected_problem"] for query in queries],
    }
    # mode -> named vector. The pairing is the contract; the loop never recombines them.
    pairs = (("query", VECTOR_PROBLEM), ("sts", VECTOR_STS))

    with httpx.Client(base_url=qdrant, timeout=30.0) as qdrant_client:
        points = _collection_size(qdrant_client, collection)

        typer.echo(f"\nKolekcja '{collection}': {points} punktów, {len(queries)} zapytań\n")
        header = f"{'wejście':<12} {'tryb → wektor':<22}"

        typer.echo(f"{header} {'@1':>6} {'@3':>6} {'@5':>6} {'MRR':>7}")
        typer.echo("-" * 64)

        results: dict[tuple[str, str], tuple[list[float], float]] = {}

        for label, texts in inputs.items():
            for mode, vector_name in pairs:
                with httpx.Client(base_url=embedder, timeout=120.0) as embedder_client:
                    vectors = _embed_queries(embedder_client, texts, mode)

                ranks = _search_ranks(
                    client       = qdrant_client,
                    collection   = collection,
                    vectors      = vectors,
                    expected_ids = expected,
                    k_max        = k_max,
                    vector_name  = vector_name,
                )
                curve, mrr = _metrics(ranks, k_max)
                results[(label, mode)] = (curve, mrr)

                pair = f"{mode} → {vector_name}"
                typer.echo(
                    f"{label:<12} {pair:<22} "
                    f"{curve[0]:6.1f} {curve[min(2, k_max - 1)]:6.1f} {curve[-1]:6.1f} {mrr:7.3f}"
                )

            typer.echo("")

    # --- co z tego wynika ---
    typer.echo("Różnica query→passage minus sts→sts:")

    for label in inputs:
        query_curve, query_mrr = results[(label, "query")]
        sts_curve,   sts_mrr   = results[(label, "sts")]

        typer.echo(
            f"  {label:<12} @1: {query_curve[0] - sts_curve[0]:+.1f} pp"
            f"    MRR: {query_mrr - sts_mrr:+.3f}"
        )


if __name__ == "__main__":
    cli()
