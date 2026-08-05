"""Measure recall@5 of embedding models on the golden set, across models and prefix modes.

Do czego:
    Rozstrzyga dwie decyzje, których etap 2 świadomie nie podjął: KTÓRY MODEL i KTÓRY TRYB.
    Obie zapadają pomiarem, nie z góry — i to ten pomiar kasuje jeden z dwóch named vectors
    (CLAUDE.md -> „Wybór modelu embeddingowego i trybu — mierzyć, nie zgadywać").

    Skrypt jest repo-level: nie odpytuje usługi `embedder` i nie stawia stacku, bo ładuje modele
    wprost. Importuje jednak `app.domain` — po to, żeby tekst do embeddingu budował TA SAMA
    metoda co przyszła indeksacja (`ParsedTicket.embedding_text()`). Sklejenie go tutaj ręcznie
    dałoby wynik opisujący coś innego niż produkt.

Flow:
    1. Wczytuje golden set (`data/golden/<zestaw>.json`) i artefakty korpusu.
    2. Dla każdego modelu ładuje wagi raz, po czym dla każdego trybu:
       - embeduje CAŁY korpus jako dokumenty (także rekordy odrzucone — są dystraktorami),
       - embeduje zapytania,
       - liczy podobieństwo kosinusowe i sprawdza, czy oczekiwany rekord jest w top-K.
    3. Drukuje tabelę: model × tryb, z rozbiciem per gatunek zapytania i per trudność.

Zasady:
    - **Prefiksy per model, nie globalnie.** PolDense używa `[query]: `/`[sts]: `, Nomic
      `search_query: `/`search_document: `, BGE-M3 żadnych. Porównanie „PolDense z prefiksami
      vs Nomic bez" mierzyłoby nasz błąd, nie modele.
    - **Korpus przeszukiwany jest NIEPRZEFILTROWANY** — rekordy bez wiedzy zostają jako
      dystraktory, bo w produkcji filtr etapu 4 też nie będzie doskonały.
    - **Normalizacja wektorów jest nasza**, tak samo jak w `SentenceTransformerEncoder`:
      PolDense nie ma modułu `Normalize`, więc bez tego progi znaczyłyby co innego niż
      na produkcji.
"""

import json
import pathlib
import statistics
import sys
import time
from collections import defaultdict

import numpy as np
import typer
from sentence_transformers import SentenceTransformer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# `app` mieszka w api/ i nie jest na ścieżce przy uruchomieniu `python scripts/...`.
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.domain.ticket import ParsedTicket  # noqa: E402  (import po ustawieniu sys.path)

DEFAULT_GOLDEN = REPO_ROOT / "data" / "golden" / "bielik-11b-golden200.json"

# Tryby prefiksów PER MODEL. Klucz to nazwa modelu na HF, wartość to mapowanie
# rola -> prefiks. `document` jest tym, co w naszym kontrakcie nazywa się `passage`.
#
# Rozjazd wobec `MODE_PREFIXES` w embedderze jest zamierzony: tam obsługujemy JEDEN model
# skonfigurowany przez ENV, tutaj porównujemy kilka naraz, więc tabela musi być dwupoziomowa.
# Gdy pomiar wskaże zwycięzcę, jego wiersz stąd trafia do embeddera i ta tabela znika.
MODEL_PREFIXES: dict[str, dict[str, str]] = {
    # PolDense: `[query]: ` z config_sentence_transformers.json, `[sts]: ` z karty modelu
    # (w konfiguracji go NIE MA — pole `prompts` opisuje asymetrię, a STS jest symetryczny).
    "OPI-PIB/PolDense-150M": {
        "query": "[query]: ", "document": "", "sts": "[sts]: ",
    },
    "OPI-PIB/PolDense-68M": {
        "query": "[query]: ", "document": "", "sts": "[sts]: ",
    },
    # mmlw: prefiks po stronie zapytania, dokumenty gołe. Do potwierdzenia na karcie modelu
    # przed pomiarem — wpisane z pamięci, a to jest dokładnie ten rodzaj wartości, który
    # przekrzywia porównanie, gdy się go zgadnie.
    "sdadas/mmlw-roberta-large": {
        "query": "zapytanie: ", "document": "", "sts": "",
    },
    # BGE-M3 nie używa prefiksów w ogóle — i ma własny moduł Normalize, więc nasza normalizacja
    # jest tam redundantna (nigdy szkodliwa: dzielenie przez 1).
    "BAAI/bge-m3": {
        "query": "", "document": "", "sts": "",
    },
    # Nomic: wariant v2-moe (wielojęzyczny), nie v1.5. Ma trzy własne prefiksy, w tym osobny
    # `clustering: ` dla porównań symetrycznych.
    "nomic-ai/nomic-embed-text-v2-moe": {
        "query": "search_query: ", "document": "search_document: ", "sts": "clustering: ",
    },
    # GRUPA KONTROLNA, nie kandydat. v1.5 jest trenowany prawie wyłącznie na angielskim, więc na
    # polskim korpusie POWINIEN wypaść wyraźnie słabiej. Jeśli mimo to trafia ~95%, dowodzi to,
    # że zadanie nie wymaga dobrego modelu — czyli że pomiar nie różnicuje kandydatów i trzeba go
    # utrudnić (większy korpus, ostrzejsze zapytania), zanim cokolwiek na jego podstawie wybierzemy.
    "nomic-ai/nomic-embed-text-v1.5": {
        "query": "search_query: ", "document": "search_document: ", "sts": "clustering: ",
    },
}

DEFAULT_MODELS = ["OPI-PIB/PolDense-150M"]

cli = typer.Typer(help="Pomiar recall@K embedderów na golden secie.")

HELP_COMMAND = "Liczy recall@K dla modeli i trybów, drukuje tabelę porównawczą."
HELP_GOLDEN  = "Plik golden setu (JSON z queries i rejected)."
HELP_MODELS  = "Model do zmierzenia; wielokrotnie. Pusto = domyślny zestaw."
HELP_K       = "Do jakiego K liczyć krzywą recall (drukowane są @1..@K)."
HELP_BATCH   = "Rozmiar partii przy embedowaniu."


def _load_corpus(
    corpus_dir: pathlib.Path,  # e.g. Path("data/parsed/bielik-11b-golden200")
) -> tuple[list[int], list[str]]:
    """
    Description:
    Reads every artifact in the directory and returns ids alongside the text that becomes their
    vector. Uses `ParsedTicket.embedding_text()` rather than joining fields here, so the measured
    text is byte-for-byte what indexing will embed.

    Example args:
        corpus_dir=Path("data/parsed/bielik-11b-golden200")

    Example result:
        ([5612, 5641], ["Brak dostępności Menu…\\nPo zalogowaniu…", "Brak możliwości…\\n…"])
    """
    ids, texts = [], []

    for path in sorted(corpus_dir.glob("*.json"), key=lambda p: int(p.stem)):
        ticket = ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))

        ids.append(int(path.stem))
        texts.append(ticket.embedding_text())

    return ids, texts


def _encode(
    model:    SentenceTransformer,  # e.g. SentenceTransformer("OPI-PIB/PolDense-150M")
    texts:    list[str],            # e.g. ["Brak tonera"]
    prefix:   str,                  # e.g. "[query]: "
    batch:    int = 32,
) -> np.ndarray:
    """
    Description:
    Embeds texts with one prefix and returns unit-length vectors. Normalisation happens here for
    the same reason it happens in `SentenceTransformerEncoder`: PolDense ships no `Normalize`
    module, so cosine scores would otherwise land in a different range than in production.

    Example args:
        model=SentenceTransformer("OPI-PIB/PolDense-150M")
        texts=["Brak tonera"]
        prefix="[query]: "
        batch=32

    Example result:
        array([[0.0123, -0.0456, …]], dtype=float32)
    """
    return model.encode(
        [f"{prefix}{text}" for text in texts],
        batch_size           = batch,
        normalize_embeddings = True,
        convert_to_numpy     = True,
        show_progress_bar    = False,
    )


def _ranks(
    query_vectors:  np.ndarray,  # e.g. shape (165, 768)
    corpus_vectors: np.ndarray,  # e.g. shape (200, 768)
    corpus_ids:     list[int],   # e.g. [5612, 5641, …]
    expected_ids:   list[int],   # e.g. [5641, 5656, …] — one per query, in order
) -> list[int]:
    """
    Description:
    Returns, for each query, the 1-based POSITION at which its expected record was ranked. Rank
    rather than a boolean hit, because one number answers every question we have: recall@K is
    `rank <= K`, and MRR is the mean of `1/rank`. A boolean would throw away the distinction
    between "first" and "fifth" — which is exactly what separates models once recall@5 saturates.

    A plain dot product is the cosine similarity here, because both sides are unit-length.

    Example args:
        query_vectors=array of shape (2, 768)
        corpus_vectors=array of shape (200, 768)
        corpus_ids=[5612, 5641]
        expected_ids=[5641, 5612]

    Example result:
        [1, 7]
    """
    # Jedna macierz zamiast pętli po zapytaniach: przy 165 × 200 to ułamek sekundy, a kod czyta
    # się jak definicja metryki.
    similarity = query_vectors @ corpus_vectors.T

    # Pełne sortowanie, nie `argpartition`: potrzebna jest POZYCJA, a nie sam skład top-K.
    # Przy tej skali koszt jest nieodczuwalny, a kod pozostaje jednoznaczny.
    order    = np.argsort(-similarity, axis=1)
    index_of = {ticket_id: position for position, ticket_id in enumerate(corpus_ids)}

    ranks = []

    for row, expected in zip(order, expected_ids, strict=True):
        # `nonzero` zwraca pozycję w posortowanej kolejności; +1, bo rangi liczymy od jedynki.
        ranks.append(int(np.nonzero(row == index_of[expected])[0][0]) + 1)

    return ranks


def _metrics(
    ranks: list[int],  # e.g. [1, 3, 7]
    k_max: int = 5,
) -> tuple[list[float], float]:
    """
    Description:
    Turns ranks into the recall CURVE (recall@1 … recall@k_max) plus MRR. The curve rather than a
    single recall@5, because recall saturates on a small corpus — 100% at K=5 says nothing, while
    the shape between K=1 and K=5 still separates a model that ranks first from one that ranks
    fifth. MRR compresses the same information into one comparable number.

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
    label:   str,         # e.g. "query→passage"
    ranks:   list[int],   # e.g. [1, 3, 7]
    queries: list[dict],  # e.g. [{"kind": "eksploatacyjne", "difficulty": "typowe"}, …]
    k_max:   int = 5,
) -> None:
    """
    Description:
    Prints the recall curve and MRR for one mode, then the same figures split by query kind and
    difficulty. The split is the point — a model good at operational queries and weak at
    deployment ones is a product fact a single number would hide.

    Example args:
        label="query→passage"
        ranks=[1, 3, 7]
        queries=[{"kind": "eksploatacyjne", "difficulty": "typowe"}, …]
        k_max=5

    Example result:
        None (kilka wierszy tabeli na stdout)
    """
    def line(name: str, subset: list[int]) -> str:
        curve, mrr = _metrics(subset, k_max)
        cells      = "  ".join(f"{value:5.1f}" for value in curve)

        return f"    {name:<26} {cells}   MRR {mrr:.3f}  (n={len(subset)})"

    header = "  ".join(f"@{k:<4}" for k in range(1, k_max + 1))

    typer.echo(f"  {label}")
    typer.echo(f"    {'':<26} {header}")
    typer.echo(line("razem", ranks))

    by_group: dict[str, list[int]] = defaultdict(list)

    for rank, query in zip(ranks, queries, strict=True):
        by_group[query["kind"]].append(rank)
        by_group[query["difficulty"]].append(rank)

    for group in ("eksploatacyjne", "wdrożeniowo-migracyjne", "typowe", "trudne"):
        if by_group.get(group):
            typer.echo(line(group, by_group[group]))


@cli.callback()
def main() -> None:
    """
    Description:
    Groups the subcommands so Typer keeps the command tree even with a single command.

    Example args:
        (brak)

    Example result:
        None
    """


@cli.command(help=HELP_COMMAND)
def recall(
    golden: pathlib.Path = typer.Option(DEFAULT_GOLDEN, "--golden", help=HELP_GOLDEN),
    models: list[str]    = typer.Option(None,           "--model",  help=HELP_MODELS),
    k:      int          = typer.Option(5,              "--k",      help=HELP_K),
    batch:  int          = typer.Option(32,             "--batch",  help=HELP_BATCH),
) -> None:
    """
    Description:
    Runs the measurement and prints a table of recall@K per model and mode. Two modes are
    compared: asymmetric retrieval (`query→passage`) and symmetric similarity (`sts→sts`) —
    which of them wins is genuinely open (CLAUDE.md -> „Embeddingi").

    Example args:
        golden=Path("data/golden/bielik-11b-golden200.json")
        models=["OPI-PIB/PolDense-150M"]
        k=5
        batch=32

    Example result:
        None (tabela na stdout)

    Raises:
        typer.Exit: golden set albo katalog korpusu nie istnieje
    """
    if not golden.exists():
        typer.echo(f"Brak golden setu: {golden}", err=True)

        raise typer.Exit(code=1)

    data       = json.loads(golden.read_text(encoding="utf-8"))
    queries    = data["queries"]
    corpus_dir = REPO_ROOT / data["meta"]["corpus_dir"]

    if not corpus_dir.exists():
        typer.echo(f"Brak katalogu korpusu: {corpus_dir}", err=True)

        raise typer.Exit(code=1)

    corpus_ids, corpus_texts = _load_corpus(corpus_dir)
    query_texts  = [q["query_raw"] for q in queries]
    expected_ids = [q["expected_ticket_id"] for q in queries]

    lengths = [len(t) for t in query_texts]

    typer.echo(f"Golden set: {golden.name}")
    typer.echo(f"  zapytań: {len(queries)}, korpus: {len(corpus_ids)} rekordów (z dystraktorami)")
    typer.echo(f"  długość zapytania: mediana {statistics.median(lengths):.0f} zn.")
    typer.echo("")

    for model_name in (models or DEFAULT_MODELS):
        prefixes = MODEL_PREFIXES.get(model_name)

        if prefixes is None:
            typer.echo(f"{model_name}: BRAK WPISU w MODEL_PREFIXES — pomijam.", err=True)
            typer.echo("  Dopisz prefiksy tego modelu, inaczej pomiar zmierzy nasz błąd.", err=True)

            continue

        typer.echo(f"{model_name}")

        # Postęp drukowany jawnie, bo paski `sentence-transformers` są wyłączone (zaśmiecają
        # wynik), a pierwsze uruchomienie modelu POBIERA WAGI — kilkaset MB do 2 GB. Bez tych
        # komunikatów przebieg jest nieodróżnialny od zawieszenia.
        # Każdy komunikat to PEŁNA linia, nigdy `nl=False`: niedomknięta linia zostaje w buforze
        # stdout i nie pojawia się na ekranie, dopóki nie dopiszemy do niej reszty — czyli
        # dokładnie przez ten czas, w którym postęp jest potrzebny. `flush` z tego samego powodu.
        typer.echo("  ładowanie modelu (pierwszy raz = pobranie wag)…")
        sys.stdout.flush()

        started = time.monotonic()
        model   = SentenceTransformer(model_name)
        vectors = model.get_embedding_dimension()

        typer.echo(f"    gotowe w {time.monotonic() - started:.0f}s, wymiar {vectors}")
        sys.stdout.flush()

        # --- oś trybu ---
        # Dokumenty embedujemy raz per tryb, zapytania raz per tryb; obie strony MUSZĄ być
        # w tej samej przestrzeni (CLAUDE.md: „nie wolno mieszać stron").
        for label, query_prefix, doc_prefix in (
            ("query→passage", prefixes["query"], prefixes["document"]),
            ("sts→sts",       prefixes["sts"],   prefixes["sts"]),
        ):
            typer.echo(f"  {label}: embeduję korpus ({len(corpus_texts)} rekordów)…")
            sys.stdout.flush()

            started        = time.monotonic()
            corpus_vectors = _encode(model, corpus_texts, doc_prefix, batch)

            typer.echo(f"    korpus gotowy w {time.monotonic() - started:.0f}s")
            typer.echo(f"  {label}: embeduję zapytania ({len(query_texts)})…")
            sys.stdout.flush()

            started       = time.monotonic()
            query_vectors = _encode(model, query_texts, query_prefix, batch)

            typer.echo(f"    zapytania gotowe w {time.monotonic() - started:.0f}s")
            sys.stdout.flush()

            ranks = _ranks(query_vectors, corpus_vectors, corpus_ids, expected_ids)

            _report(label, ranks, queries, k)

        typer.echo("")

    typer.echo("Uwaga: oś „zapytanie surowe vs sparsowane\" wymaga przebiegu LLM po zapytaniach")
    typer.echo("i jest osobnym pomiarem — tutaj zapytania idą SUROWE, jak wpływają do helpdesku.")


if __name__ == "__main__":
    cli()
