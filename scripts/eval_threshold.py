"""Measure where to put RAG_SCORE_MIN — the cost/benefit table, not a single number.

WYMAGA ZBUDOWANEGO INDEKSU I CHODZĄCEGO STACKU:

    docker compose up -d                          # embedder + qdrant
    helpdesk rag index data/parsed/<zestaw>       # napełnij kolekcję
    python scripts/eval_threshold.py table        # tabela koszt/zysk per próg
    python scripts/eval_threshold.py detail       # rozbicie per dystraktor i lista strat
    python scripts/eval_threshold.py plot         # wykres obu rozkładów z linią progu (PNG)

Do czego:
    Próg odcina trafienia poniżej score. Ustawiony za nisko przepuszcza śmieci, które WYGLĄDAJĄ na
    odpowiedź; za wysoko wycina trafienia poprawne i zamienia je w fałszywe „nowy typ problemu".
    Ten skrypt liczy obie strony naraz, na dwóch niezależnych zbiorach:

        A. golden set  — zapytania, które MAJĄ swój rekord w indeksie (górna granica: czego nie
           wolno odciąć),
        B. dystraktory — zapytania, które NIE mają (dolna granica: co chcemy odciąć).

    Bez B pomiar nie istnieje: golden set zawiera wyłącznie zapytania z celem, więc sam pokazuje
    tylko, jak nisko schodzą trafienia poprawne — nigdy, jak wysoko wchodzą śmieci.

Dwie miary po stronie dystraktorów, bo mierzą CO INNEGO:
    - **zapytania wyciszone całkiem** — ile dystraktorów nie zwróciło ANI JEDNEGO trafienia nad
      progiem. To jest rezultat: użytkownik dostaje uczciwą pustkę.
    - **trafienia odcięte** — ile pojedynczych trafień wypadło, w sumie po wszystkich zapytaniach.
      To jest postęp, nie rezultat: dystraktor skrócony z pięciu śmieci do jednego dalej wygląda
      jak odpowiedź. Miara pomocnicza — pierwsza rozstrzyga.
    Pierwszej NIE DA SIĘ odtworzyć z drugiej: ta sama suma odciętych trafień odpowiada i sytuacji
    „13 zapytań pustych, 3 pełne", i „wszystkie 16 zachowało po jednym".

Dlaczego score krótkich zapytań jest niski (pomiar 2026-08-20, kluczowe przy czytaniu wyników):
    Najgorzej punktowane trafienia POPRAWNE to te najkrótsze — „Nie da się zakładać nowych spraw"
    wobec „Nie ma możliwości zakładania spraw" daje 0,499, choć to praktycznie jedno zdanie. Krótki
    tekst po obu stronach daje mniejszy cosinus niż dwa długie o luźnym związku. To własność miary,
    nie jakości trafienia — dlatego progu nie wolno stroić samą liczbą „ile procent zachowanych".

Adresy usług są argumentami (`--embedder`, `--qdrant`) i domyślnie wskazują **porty hosta**
publikowane przez compose, nie nazwy z sieci compose: skrypt jest repo-level i chodzi obok stacku.
"""

import json
import pathlib
import statistics
import sys

import httpx
import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# `app` mieszka w api/ i nie jest na ścieżce przy uruchomieniu `python scripts/...`.
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.retrieval.model_point import VECTOR_PROBLEM  # noqa: E402  (po sys.path)

DEFAULT_GOLDEN      = REPO_ROOT / "data" / "golden" / "bielik-11b-golden200.json"
DEFAULT_DISTRACTORS = REPO_ROOT / "data" / "golden" / "distractors.json"

# Adresy z HOSTA, nie z sieci compose — jak w eval_index.py.
DEFAULT_EMBEDDER = "http://localhost:8001"
DEFAULT_QDRANT   = "http://localhost:6333"

DEFAULT_PLOT_OUT = REPO_ROOT / "data" / "docs" / "pomiar-progu-score.png"

EMBED_BATCH_SIZE = 32

# --- wykres ---
# Szerokość kubełka histogramu. 0,01 daje ~35 słupków na zajętym paśmie score — dość, żeby widać
# było kształt, za mało, żeby rozsypać się na pojedyncze obserwacje przy 80-elementowej serii.
BIN_WIDTH = 0.01

# Paleta: niebieski = trafienia poprawne, pomarańczowy = śmieci. Rozróżnialne także w druku
# czarno-białym (różna jasność) i przy najczęstszej wadzie widzenia barw.
COLOR_GOOD      = "#2a6f97"
COLOR_BAD       = "#e07a3f"
COLOR_THRESHOLD = "#b3243c"

# Zakres kandydatów na próg. Dolna granica to wartość, poniżej której próg nic nie robi; górna —
# powyżej której traci już co dziesiąte trafienie poprawne. Krok 0,02, bo przy 162 zapytaniach
# jedno trafienie waży 0,6 pp i drobniejszy krok pokazywałby szum.
THRESHOLD_MIN  = 0.30
THRESHOLD_MAX  = 0.60
THRESHOLD_STEP = 0.02

cli = typer.Typer(help="Pomiar progu RAG_SCORE_MIN na zbudowanym indeksie.")

HELP_TABLE  = "Tabela koszt/zysk: ile trafień poprawnych zachowanych, ile dystraktorów wyciszonych."
HELP_DETAIL = "Rozbicie per dystraktor i lista zapytań traconych przy wskazanym progu."
HELP_PLOT   = "Wykres obu rozkładów score z zaznaczoną linią progu — zapisuje PNG do raportu."


def _load_queries(
    golden_path: pathlib.Path,  # e.g. Path("data/golden/bielik-11b-golden200.json")
) -> list[dict]:
    """
    Description:
    Reads golden-set queries — the ones that DO have a target in the index.

    Example args:
        golden_path=Path("data/golden/bielik-11b-golden200.json")

    Example result:
        [{"expected_ticket_id": 5641, "query_raw": "Dzień dobry, nie mogę…", …}]
    """
    return json.loads(golden_path.read_text(encoding="utf-8"))["queries"]


def _load_distractors(
    distractors_path: pathlib.Path,  # e.g. Path("data/golden/distractors.json")
) -> list[dict]:
    """
    Description:
    Reads distractor queries — the ones whose correct answer is NO hit at all.

    Example args:
        distractors_path=Path("data/golden/distractors.json")

    Example result:
        [{"id": "D01", "class": "spoza_modulu", "query_raw": "Dzień dobry, w Kartach…"}]
    """
    return json.loads(distractors_path.read_text(encoding="utf-8"))["queries"]


def _embed(
    client: httpx.Client,  # e.g. httpx.Client(base_url="http://localhost:8001")
    texts:  list[str],     # e.g. ["Dzień dobry, nie mogę podpisać pisma…"]
) -> list[list[float]]:
    """
    Description:
    Embeds queries through the running `embedder` in `query` mode, in batches.

    Mode is fixed, not a parameter: stage 4 settled search on `query`→`passage` for both raw and
    parsed queries, and a threshold measured in another mode would describe a system we do not run.

    Example args:
        client=httpx.Client(base_url="http://localhost:8001")
        texts=["Dzień dobry, nie mogę podpisać pisma…"]

    Example result:
        [[0.0123, -0.0456, …]]

    Raises:
        typer.Exit: code 2 when the embedder is unreachable
    """
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]

        try:
            response = client.post("/embed", json={"texts": batch, "mode": "query"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            typer.echo(
                f"BŁĄD: nie ma kontaktu z embedderem ({client.base_url}): {exc}\n"
                f"       Podnieś stack: `docker compose up -d`.",
                err=True,
            )
            raise typer.Exit(code=2) from exc

        vectors.extend(response.json()["vectors"])

    return vectors


def _search(
    client:     httpx.Client,       # e.g. httpx.Client(base_url="http://localhost:6333")
    collection: str,                # e.g. "tickets"
    vectors:    list[list[float]],  # e.g. [[0.0123, -0.0456, …]]
    top_k:      int,                # e.g. 5
) -> list[list[tuple[str, float]]]:
    """
    Description:
    Returns, per query, the top-K hits as (ticket_id, score) pairs.

    Scores come back RAW — no threshold is applied here on purpose. Filtering happens later, in
    pure arithmetic over these numbers, so every candidate threshold is evaluated against the same
    single retrieval run instead of re-querying Qdrant sixteen times.

    Example args:
        client=httpx.Client(base_url="http://localhost:6333")
        collection="tickets"
        vectors=[[0.0123, -0.0456]]
        top_k=5

    Example result:
        [[("5641", 0.612), ("5656", 0.494)]]
    """
    results = []

    for vector in vectors:
        response = client.post(
            f"/collections/{collection}/points/search",
            json={
                # Named vector spelled explicitly: the collection holds two and searching the wrong
                # one returns plausible-looking nonsense rather than an error.
                "vector":       {"name": VECTOR_PROBLEM, "vector": vector},
                "limit":        top_k,
                "with_payload": True,
            },
        )
        response.raise_for_status()

        results.append(
            [(str(hit["payload"]["ticket_id"]), hit["score"]) for hit in response.json()["result"]]
        )

    return results


def _collection_size(
    client:     httpx.Client,  # e.g. httpx.Client(base_url="http://localhost:6333")
    collection: str,           # e.g. "tickets"
) -> int:
    """
    Description:
    Returns how many points the collection holds, refusing to go on when there is nothing to
    measure — a report of zeros would look like a threshold problem rather than a missing index.

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


def _correct_scores(
    hits:         list[list[tuple[str, float]]],  # e.g. [[("5641", 0.612), ("5656", 0.494)]]
    expected_ids: list[str],                      # e.g. ["5641"]
) -> list[float | None]:
    """
    Description:
    Picks, per query, the score of the record the golden set expects — or None when it did not come
    back in top-K at all.

    None is NOT the same as a low score and must not collapse into one: a record missing from top-K
    is already lost before any threshold applies, so counting it as "cut by the threshold" would
    blame the threshold for a retrieval miss.

    Example args:
        hits=[[("5641", 0.612), ("5656", 0.494)]]
        expected_ids=["5641"]

    Example result:
        [0.612]
    """
    scores: list[float | None] = []

    for query_hits, expected in zip(hits, expected_ids, strict=True):
        scores.append(next((score for tid, score in query_hits if tid == expected), None))

    return scores


def _thresholds() -> list[float]:
    """
    Description:
    Builds the list of candidate thresholds to evaluate.

    Example args:
        (none)

    Example result:
        [0.3, 0.32, 0.34, …, 0.6]
    """
    steps = int(round((THRESHOLD_MAX - THRESHOLD_MIN) / THRESHOLD_STEP)) + 1

    return [round(THRESHOLD_MIN + THRESHOLD_STEP * i, 2) for i in range(steps)]


def _distribution(
    name:   str,                   # e.g. "A: rekord poprawny"
    values: list[float],           # e.g. [0.612, 0.494, 0.551]
) -> str:
    """
    Description:
    Formats one score series as a percentile line.

    Percentiles rather than min/max alone, because the two series OVERLAP at their edges while
    their bulks are cleanly apart — reading only the extremes suggests no threshold can work,
    which is exactly the wrong conclusion.

    Example args:
        name="A: rekord poprawny"
        values=[0.612, 0.494, 0.551]

    Example result:
        "A: rekord poprawny    n=162  min 0.409  p05 0.499  med 0.597  p95 0.673  max 0.702"
    """
    ordered = sorted(values)
    pick    = lambda frac: ordered[min(len(ordered) - 1, int(frac * len(ordered)))]  # noqa: E731

    return (
        f"{name:<22} n={len(ordered):3d}  min {ordered[0]:.3f}  p05 {pick(0.05):.3f}  "
        f"p25 {pick(0.25):.3f}  med {statistics.median(ordered):.3f}  "
        f"p75 {pick(0.75):.3f}  p95 {pick(0.95):.3f}  max {ordered[-1]:.3f}"
    )


@cli.callback()
def main() -> None:
    """
    Description:
    Root callback. Keeps Typer in subcommand mode even with two commands, so invoking either stays
    explicit.

    Example args:
        (none)

    Example result:
        None
    """


def _measure(
    collection:  str,           # e.g. "tickets"
    golden:      pathlib.Path,  # e.g. Path("data/golden/bielik-11b-golden200.json")
    distractors: pathlib.Path,  # e.g. Path("data/golden/distractors.json")
    embedder:    str,           # e.g. "http://localhost:8001"
    qdrant:      str,           # e.g. "http://localhost:6333"
    top_k:       int,           # e.g. 5
) -> tuple[int, list[dict], list[float | None], list[dict], list[list[tuple[str, float]]]]:
    """
    Description:
    Runs both retrieval passes once and hands back everything either command needs: collection
    size, the golden queries with their correct-record scores, and the distractors with their raw
    hits.

    Shared by both commands so the two reports can never disagree about the same index.

    Example args:
        collection="tickets"
        golden=Path("data/golden/bielik-11b-golden200.json")
        distractors=Path("data/golden/distractors.json")
        top_k=5

    Example result:
        (171, [{…}], [0.612, None], [{…}], [[("34004", 0.488)]])

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    queries      = _load_queries(golden)
    distractor_q = _load_distractors(distractors)

    with httpx.Client(base_url=qdrant, timeout=60.0) as qdrant_client:
        points = _collection_size(qdrant_client, collection)

        with httpx.Client(base_url=embedder, timeout=300.0) as embedder_client:
            golden_vectors     = _embed(embedder_client, [q["query_raw"] for q in queries])
            distractor_vectors = _embed(embedder_client, [q["query_raw"] for q in distractor_q])

        golden_hits     = _search(qdrant_client, collection, golden_vectors, top_k)
        distractor_hits = _search(qdrant_client, collection, distractor_vectors, top_k)

    correct = _correct_scores(golden_hits, [str(q["expected_ticket_id"]) for q in queries])

    return points, queries, correct, distractor_q, distractor_hits


@cli.command("table", help=HELP_TABLE)
def table(
    collection:  str          = typer.Option("tickets", help="Kolekcja Qdranta do przeszukania."),
    golden:      pathlib.Path = typer.Option(DEFAULT_GOLDEN, help="Plik golden setu."),
    distractors: pathlib.Path = typer.Option(DEFAULT_DISTRACTORS, help="Plik dystraktorów."),
    embedder:    str          = typer.Option(DEFAULT_EMBEDDER, help="Adres usługi embeddera."),
    qdrant:      str          = typer.Option(DEFAULT_QDRANT, help="Adres Qdranta."),
    top_k:       int          = typer.Option(5, help="Ile trafień pobierać (jak RAG_TOP_K)."),
) -> None:
    """
    Description:
    Prints the score distributions of both series and the cost/benefit table across candidate
    thresholds.

    Example args:
        collection="tickets"
        top_k=5

    Example result:
        prints two percentile lines and one table row per candidate threshold

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    points, queries, correct, distractor_q, distractor_hits = _measure(
        collection, golden, distractors, embedder, qdrant, top_k
    )

    found      = [score for score in correct if score is not None]
    total_hits = sum(len(hits) for hits in distractor_hits)

    typer.echo(f"\nKolekcja '{collection}': {points} punktów")
    typer.echo(f"A: {len(queries)} zapytań golden setu · B: {len(distractor_q)} dystraktorów\n")

    # --- rozkłady obu serii ---
    typer.echo(_distribution("A: rekord poprawny", found))
    typer.echo(
        _distribution("B: dystraktor top-1", [hits[0][1] for hits in distractor_hits if hits])
    )

    # --- tabela koszt/zysk ---
    typer.echo("\nPRÓG | poprawne zachowane | dystraktory wyciszone | trafienia dystraktorów")
    typer.echo(
        f"     | (z {len(queries):>3})            "
        f"| całkiem (z {len(distractor_q):>2})        "
        f"| odcięte (z {total_hits})"
    )
    typer.echo("-" * 78)

    for threshold in _thresholds():
        kept     = sum(1 for score in correct if score is not None and score >= threshold)
        silenced = sum(1 for hits in distractor_hits if all(s < threshold for _, s in hits))
        cut      = sum(1 for hits in distractor_hits for _, s in hits if s < threshold)

        typer.echo(
            f"{threshold:.2f} | {kept:3d}  {100 * kept / len(queries):5.1f}%        "
            f"| {silenced:2d}  {100 * silenced / len(distractor_q):5.1f}%          "
            f"| {cut:2d}/{total_hits}  {100 * cut / total_hits:5.1f}%"
        )

    typer.echo(
        "\nUWAGA: seria A jest OPTYMISTYCZNA — golden set i korpus to ten sam zbiór rekordów,\n"
        "       więc każde zapytanie ma tam swój cel. W produkcji część zapytań celu nie ma\n"
        "       (47% korpusu to singletony), więc realny rozkład będzie gorszy, nie lepszy."
    )
    typer.echo(
        f"UWAGA: próg zmierzony na {points} rekordach jest DOLNYM oszacowaniem — przy większym\n"
        "       korpusie score dystraktorów rośnie. Powtórzyć po etapie 10 (~1100 rekordów)."
    )


@cli.command("detail", help=HELP_DETAIL)
def detail(
    threshold:   float        = typer.Option(0.48, help="Próg, dla którego wypisać straty."),
    collection:  str          = typer.Option("tickets", help="Kolekcja Qdranta do przeszukania."),
    golden:      pathlib.Path = typer.Option(DEFAULT_GOLDEN, help="Plik golden setu."),
    distractors: pathlib.Path = typer.Option(DEFAULT_DISTRACTORS, help="Plik dystraktorów."),
    embedder:    str          = typer.Option(DEFAULT_EMBEDDER, help="Adres usługi embeddera."),
    qdrant:      str          = typer.Option(DEFAULT_QDRANT, help="Adres Qdranta."),
    top_k:       int          = typer.Option(5, help="Ile trafień pobierać (jak RAG_TOP_K)."),
) -> None:
    """
    Description:
    Shows what a given threshold actually does: every distractor with its individual scores, and
    every golden query whose correct record would be cut.

    The list of losses is the part that decides. A percentage cannot tell whether the cut records
    are marginal or are near-identical restatements sitting at rank 1 — and in this corpus it is
    the second (short texts score low regardless of how well they match).

    Example args:
        threshold=0.48
        collection="tickets"

    Example result:
        prints one line per distractor plus the queries lost at that threshold

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    _points, queries, correct, distractor_q, distractor_hits = _measure(
        collection, golden, distractors, embedder, qdrant, top_k
    )

    # --- co robi próg z każdym dystraktorem ---
    typer.echo(f"\nDystraktory przy progu {threshold:.2f} (score kolejnych trafień):\n")

    for query, hits in zip(distractor_q, distractor_hits, strict=True):
        scores  = " ".join(f"{score:.3f}" for _, score in hits)
        passing = sum(1 for _, score in hits if score >= threshold)
        verdict = "WYCISZONY" if passing == 0 else f"przechodzi {passing}"

        typer.echo(f"  {query['id']:<5} {query['class']:<18} {scores:<36} {verdict}")

    # --- co próg kosztuje po stronie poprawnych ---
    lost = [
        (query, score)
        for query, score in zip(queries, correct, strict=True)
        if score is not None and score < threshold
    ]
    missing = sum(1 for score in correct if score is None)

    typer.echo(f"\nTracone trafienia poprawne przy progu {threshold:.2f}: {len(lost)}\n")

    for query, score in sorted(lost, key=lambda pair: pair[1]):
        typer.echo(f"  {query['expected_ticket_id']:>6}  score {score:.3f}")
        typer.echo(f"          Q: {query['query_raw'][:96]}")
        typer.echo(f"          P: {query['expected_problem'][:96]}")

    if missing:
        typer.echo(
            f"\n(poza tym {missing} zapytań nie znalazło celu w top-{top_k} — to strata"
            f" retrievalu, nie progu)"
        )


@cli.command("plot", help=HELP_PLOT)
def plot(
    out:         pathlib.Path = typer.Option(DEFAULT_PLOT_OUT, help="Gdzie zapisać PNG."),
    threshold:   float        = typer.Option(0.48, help="Próg do zaznaczenia pionową linią."),
    collection:  str          = typer.Option("tickets", help="Kolekcja Qdranta do przeszukania."),
    golden:      pathlib.Path = typer.Option(DEFAULT_GOLDEN, help="Plik golden setu."),
    distractors: pathlib.Path = typer.Option(DEFAULT_DISTRACTORS, help="Plik dystraktorów."),
    embedder:    str          = typer.Option(DEFAULT_EMBEDDER, help="Adres usługi embeddera."),
    qdrant:      str          = typer.Option(DEFAULT_QDRANT, help="Adres Qdranta."),
    top_k:       int          = typer.Option(5, help="Ile trafień pobierać (jak RAG_TOP_K)."),
) -> None:
    """
    Description:
    Draws both score distributions as overlapping histograms with the threshold marked, and saves
    it as a PNG for the report.

    What it adds over `table`: the table says how much each threshold COSTS, the figure shows why a
    threshold works at all — the two series form separate clusters even though their tails touch.
    Reading only the min/max of both series suggests they overlap hopelessly; the shape says
    otherwise, and that difference decided this measurement.

    Example args:
        out=Path("data/docs/pomiar-progu-score.png")
        threshold=0.48

    Example result:
        None — writes the PNG and prints where it went

    Raises:
        typer.Exit: the collection is missing or empty, or a service is unreachable
    """
    # Matplotlib importowany LENIWIE, wewnątrz komendy: `table` i `detail` go nie wołają, a jest to
    # najcięższa zależność tego skryptu (~1 s importu wraz z backendem). Ten sam powód co przy SDK
    # dostawców LLM w `llm/factory.py` (CLAUDE.md -> "Styl kodu").
    import matplotlib

    # Bez interaktywnego backendu: skrypt tylko zapisuje plik, a domyślny backend na maszynie bez
    # X-a wywala się przy imporcie pyplota.
    matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    _points, _queries, correct, _distractor_q, distractor_hits = _measure(
        collection, golden, distractors, embedder, qdrant, top_k
    )

    # --- dwie serie: trafienia poprawne wobec WSZYSTKICH trafień dystraktorów ---
    # Po stronie śmieci liczą się wszystkie pięć trafień każdego dystraktora, nie samo top-1: próg
    # tnie pojedyncze trafienia, więc to one są jednostką rozkładu.
    good = [score for score in correct if score is not None]
    bad  = [score for hits in distractor_hits for _, score in hits]

    # Kubełki na PEŁNEJ skali cosinusa dla wektorów jednostkowych (0..1), nie na zakresie danych:
    # oś przycięta do obserwacji rozciąga oba skupiska i każe im wyglądać na bardziej rozdzielone,
    # niż są. Czytelnik ma widzieć, że cała gra toczy się w wąskim paśmie 0,35-0,70.
    edges = [BIN_WIDTH * i for i in range(int(1 / BIN_WIDTH) + 1)]

    figure, axes = plt.subplots(figsize=(9, 4.5))

    # `weights` zamiast `density`: chcemy procent obserwacji w kubełku, a nie gęstość
    # prawdopodobieństwa — ta ostatnia skaluje się szerokością kubełka i czyta się mylnie.
    # Procent KAŻDEJ SERII z osobna, bo serie liczą 162 i 80 wartości: surowe liczności dałyby dwa
    # razy wyższe słupki po stronie poprawnej niezależnie od kształtu.
    axes.hist(
        good,
        bins    = edges,
        weights = [100 / len(good)] * len(good),
        color   = COLOR_GOOD,
        alpha   = 0.75,
        label   = f"trafienia poprawne (n={len(good)})",
    )
    axes.hist(
        bad,
        bins    = edges,
        weights = [100 / len(bad)] * len(bad),
        color   = COLOR_BAD,
        alpha   = 0.75,
        label   = f"trafienia dystraktorów (n={len(bad)})",
    )

    # --- granica ---
    axes.axvline(threshold, color=COLOR_THRESHOLD, linewidth=2, linestyle="--")
    # Etykieta pod legendą i na lewo od linii: legenda siedzi w lewym górnym rogu, a garb śmieci
    # zajmuje środek — to jedyne wolne miejsce, w którym nic nie zasłania słupków.
    axes.annotate(
        f"RAG_SCORE_MIN = {threshold:.2f}",
        xy         = (threshold, axes.get_ylim()[1] * 0.62),
        xytext     = (-8, 0),
        textcoords = "offset points",
        color      = COLOR_THRESHOLD,
        fontsize   = 10,
        fontweight = "bold",
        ha         = "right",
        va         = "top",
    )

    axes.set_xlim(0.0, 1.0)
    axes.set_xlabel("podobieństwo do zapytania (cosinus)")
    axes.set_ylabel("% trafień w serii")
    axes.set_title("Rozkład score: trafienia poprawne wobec śmieci")
    axes.legend(loc="upper left", frameon=False)
    axes.spines[["top", "right"]].set_visible(False)
    axes.grid(axis="y", alpha=0.2)

    figure.tight_layout()
    figure.savefig(out, dpi=200)

    typer.echo(f"Zapisano: {out}")


if __name__ == "__main__":
    cli()
