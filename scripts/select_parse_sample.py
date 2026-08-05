"""Select a stratified, reproducible sample of ticket ids from data/raw/.

Do czego:
    Wybiera próbkę zgłoszeń do sparsowania i wypisuje ich identyfikatory — nic więcej.
    Wyjście jest wejściem dla `helpdesk tickets parse -t <id> -t <id> …`, więc skrypt kończy
    się tam, gdzie zaczyna się CLI usługi.

    Skrypt jest repo-level, nie należy do usługi `api` (patrz „Warstwa CLI" w CLAUDE.md):
    nie importuje `api.app` i nie odpytuje żadnego endpointu.

Flow:
    1. `select` wczytuje `data/raw/`, odsiewa zgłoszenia już sparsowane (katalog zestawu)
       i te bez treści (`_passes_quality`).
    2. Grupuje pozostałe po kategorii i dobiera próbkę proporcjonalnie (`_pick_stratified`).
    3. Szacuje długość wątku każdego wybranego zgłoszenia i ostrzega o tych, które nie zmieszczą
       się w oknie kontekstu modelu — odmowa przed przebiegiem jest tańsza niż w jego trakcie.
    4. Wypisuje identyfikatory w formacie gotowym do wklejenia oraz podsumowanie doboru.

Zasady:
    - **Filtr jakości liczony na tekście po stripie**, nie na surowym HTML-u. Różnica jest realna:
      na całym module 1496 zgłoszeń przechodzi próg liczony na HTML-u, a 1477 na samym tekście —
      19 przechodzi wyłącznie dzięki tagom i encjom.
    - **Dobór deterministyczny** (równomierny skok po posortowanych id, bez losowania), żeby
      dwa uruchomienia z tymi samymi parametrami dały tę samą próbkę. Kategoria nie jest już
      polem schematu, ale warstwowanie po niej chroni przed próbką z jednego tematu, a skok po
      posortowanych id rozciąga ją na cały zakres dat (korpus ma rekordy unieważniane przez
      późniejsze oraz sezonowość).

Historia:
    Powstał z `scripts/prepare_parse_batch.py` (commit 8d7114e, skasowany 2026-08-01 wraz
    z końcem ręcznego parsowania w czacie). Renderowanie do tekstu i porcjowanie wypadły —
    robi to dziś `helpdesk tickets parse`. Został dobór i filtr, czyli to, czego CLI nie ma.
"""

import html
import json
import pathlib
import re
from collections import defaultdict

import typer

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
# Artefakty i zestawy ewaluacyjne stoją w DWÓCH miejscach, ale pod JEDNĄ nazwą (`--name`):
# artefakt jest jednorazowy i drogi (przebieg LLM), a golden set edytowalny i poprawiany przy
# przeglądzie, więc mieszanie ich w jednym drzewie kłóciłoby się z zasadą 7. Jedna nazwa dla
# obu, bo dwie osobne opcje rozjechałyby się przy drugim zestawie — i wtedy nie wiadomo, która
# lista identyfikatorów opisuje który katalog.
PARSED_ROOT = REPO_ROOT / "data" / "parsed"
GOLDEN_ROOT = REPO_ROOT / "data" / "golden"

# Domyślna nazwa zestawu. Zawiera model parsujący, choć TEN skrypt go nie zna — parsowanie to
# osobny krok, więc nazwa jest deklaracją intencji, nie zapisem faktu. Świadomie: tak działa już
# dziewięć katalogów porównawczych obok, a nazwa katalogu jest tym, co widać przy `ls`.
# Model faktycznie użyty zapisuje nagłówek golden setu.
DEFAULT_NAME = "bielik-11b-golden200"

MIN_CHARS = 50   # próg treści dla opisu i dla komentarza, liczony po stripie

# Znaki na token — pesymistycznie, żeby ostrzegać za wcześnie, a nie za późno. Polski tekst na
# słownikach z rodziny Llamy schodzi do ~3; przy realnym 3,5-4 ostrzeżemy o zgłoszeniu, które
# jeszcze by się zmieściło. Ta sama stała co w kliencie Ollamy, z tego samego powodu.
CHARS_PER_TOKEN = 3.0

cli = typer.Typer(help="Dobór próbki zgłoszeń do sparsowania.")

HELP_COMMAND = "Wybiera próbkę zgłoszeń i wypisuje ich identyfikatory."
HELP_NAME    = "Nazwa zestawu — katalog artefaktów i plik z identyfikatorami dostają ją oba."
HELP_COUNT   = "Ile zgłoszeń dobrać."
HELP_RAW     = "Katalog ze zgłoszeniami źródłowymi (JSON per zgłoszenie)."
HELP_CTX     = "Okno kontekstu modelu w tokenach; zgłoszenia ponad próg są zgłaszane osobno."


def _strip_html(markup: str) -> str:  # e.g. "<p>Dzie&#324; dobry</p>"
    """
    Description:
    Turns source HTML into readable plain text, preserving line structure of paragraphs and lists.
    Used only to MEASURE content here, but it must match what the parser will see — a threshold
    counted on markup would admit tickets whose text is 19 characters of tags.

    Example args:
        markup="<p>Dzień dobry,</p>\\r\\n<ol><li>Krok pierwszy</li></ol>"

    Example result:
        "Dzień dobry,\\n- Krok pierwszy"
    """
    if not markup:
        return ""

    # --- znaczniki blokowe na łamanie linii, pozycje listy na myślnik, reszta znika ---
    text = re.sub(r"<(br|/p|/li|/tr|/h[1-6])[^>]*>", "\n", markup, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\xa0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)

    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _passes_quality(ticket: dict) -> bool:  # e.g. {"zgloszenie": {...}, "komentarze": [...]}
    """
    Description:
    Tells whether a ticket has enough substance to be worth an LLM call. A LENGTH filter only —
    whether the content carries knowledge is decided later, when queries are written against it
    (stage 3.3) and by the indexing filter (stage 4).

    Example args:
        ticket={"zgloszenie": {"status": "rozwiazany", "szczegolowy_opis": "<p>...</p>"},
                "komentarze": [{"tresc": "<p>...</p>"}]}

    Example result:
        True
    """
    zgloszenie = ticket["zgloszenie"]

    # Dokus kończy zgłoszenia na `rozwiazany` (1735 z 1825); `zamkniety` ma 5 sztuk, ale jest
    # równie końcowy. Filtr po samym `zamkniety` odrzuciłby cały korpus — patrz CLAUDE.md.
    if zgloszenie["status"] not in ("rozwiazany", "zamkniety"):
        return False

    if len(_strip_html(zgloszenie["szczegolowy_opis"])) <= MIN_CHARS:
        return False

    return any(len(_strip_html(k["tresc"])) > MIN_CHARS for k in ticket["komentarze"] or [])


def _thread_chars(ticket: dict) -> int:  # e.g. {"zgloszenie": {...}, "komentarze": [...]}
    """
    Description:
    Measures the whole thread the parser will send: description plus every comment, after strip.
    Approximate by design — it feeds a warning, not a decision.

    Example args:
        ticket={"zgloszenie": {"szczegolowy_opis": "<p>Opis</p>"},
                "komentarze": [{"tresc": "<p>Komentarz</p>"}]}

    Example result:
        13
    """
    zgloszenie = ticket["zgloszenie"]
    total      = len(_strip_html(zgloszenie["szczegolowy_opis"]))

    return total + sum(len(_strip_html(k["tresc"])) for k in ticket["komentarze"] or [])


def _pick_stratified(
    by_category: dict,  # e.g. {"Błąd": [5629, 6378], "Usterka": [6409]}
    count:       int,   # e.g. 200
) -> list[int]:
    """
    Description:
    Picks ids proportionally to category size, spreading the choice evenly over sorted ids.
    No randomness at all: two runs with the same arguments must yield the same sample, because
    the golden set built from it is an artifact we come back to.

    Example args:
        by_category={"Błąd": [1, 2, 3, 4], "Usterka": [5, 6]}
        count=3

    Example result:
        [1, 3, 5]
    """
    universe = sum(len(ids) for ids in by_category.values())
    picked   = []

    # --- największe kategorie pierwsze: przy zaokrąglaniu kwot to one mają decydować o reszcie ---
    for _, ids in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        quota = max(1, round(count * len(ids) / universe))
        step  = max(1, len(ids) // quota)

        picked += [ids[i] for i in range(0, len(ids), step)][:quota]

    return sorted(set(picked))[:count]


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
def select(
    name:    str          = typer.Option(DEFAULT_NAME, "--name",    help=HELP_NAME),
    count:   int          = typer.Option(200,          "--count",   help=HELP_COUNT),
    raw_dir: pathlib.Path = typer.Option(DEFAULT_RAW,  "--raw-dir", help=HELP_RAW),
    num_ctx: int          = typer.Option(16384,        "--num-ctx", help=HELP_CTX),
) -> None:
    """
    Description:
    Selects the sample and prints everything needed to judge the run before paying for it: how
    many tickets were available, how the sample spreads over categories, and which tickets are
    too long for the model's context window. The ids land in a file named after the set, so a
    second set cannot silently overwrite the record of which sample was actually parsed.

    Example args:
        name="bielik-11b-golden200"
        count=200
        raw_dir=Path("data/raw")
        num_ctx=16384

    Example result:
        None (podsumowanie na stdout, identyfikatory w data/golden/<name>.txt)

    Raises:
        typer.Exit: when nothing is left to parse
    """
    parsed_dir = PARSED_ROOT / name
    ids_file   = GOLDEN_ROOT / f"{name}.txt"
    # --- wczytanie i odsiew ---
    # Artefakty nazywają się od identyfikatora (`33644.json`), więc nazwa pliku wystarcza za
    # wczytanie treści; katalog może jeszcze nie istnieć przy pierwszym przebiegu.
    parsed  = parsed_dir.glob("*.json") if parsed_dir.exists() else []
    already = {int(path.stem.split("-")[-1]) for path in parsed}

    by_category = defaultdict(list)
    tickets     = {}

    for path in sorted(raw_dir.glob("zgloszenie-*.json")):
        ticket     = json.loads(path.read_text(encoding="utf-8"))
        ticket_id  = ticket["zgloszenie"]["id"]

        if ticket_id in already or not _passes_quality(ticket):
            continue

        by_category[ticket["zgloszenie"]["kategoria"]].append(ticket_id)
        tickets[ticket_id] = ticket

    if not by_category:
        typer.echo("Brak zgłoszeń do sparsowania — wszystko już przerobione.", err=True)

        raise typer.Exit(code=1)

    picked = _pick_stratified(by_category, count)

    # --- kontrola okna kontekstu ---
    # Liczona PRZED przebiegiem, bo odmowa w jego trakcie kosztuje czas GPU. Zgłoszenia ponad
    # próg nie są usuwane z próbki: `tickets parse` odmówi ich sam, a my chcemy znać liczbę.
    budget    = int(num_ctx * CHARS_PER_TOKEN)
    too_long  = [i for i in picked if _thread_chars(tickets[i]) > budget]

    # --- raport ---
    available = sum(len(ids) for ids in by_category.values())

    typer.echo(f"Pominięto już sparsowanych: {len(already)}")
    typer.echo(f"Dostępnych po filtrze treści: {available}")
    typer.echo(f"Wybrano: {len(picked)}")
    typer.echo("")

    for category, ids in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
        in_sample = len([i for i in picked if i in set(ids)])

        typer.echo(f"  {category:<28} {in_sample:>4} / {len(ids)}")

    typer.echo("")

    if too_long:
        typer.echo(f"UWAGA: {len(too_long)} zgłoszeń przekracza okno {num_ctx} tokenów "
                   f"(~{budget} znaków): {', '.join(str(i) for i in too_long)}")
    else:
        typer.echo(f"Wszystkie mieszczą się w oknie {num_ctx} tokenów.")

    typer.echo("")

    # Gotowa komenda zamiast surowej listy: przy 200 zgłoszeniach same `-t <id>` to ~1700 znaków
    # w jednej linii, których nie da się zaznaczyć w terminalu. Zapis do pliku pozwala wkleić
    # jedno podstawienie, a plik zostaje jako ślad, którą próbkę faktycznie puszczono.
    GOLDEN_ROOT.mkdir(parents=True, exist_ok=True)
    ids_file.write_text("\n".join(str(i) for i in picked) + "\n", encoding="utf-8")

    typer.echo(f"Identyfikatory zapisane: {ids_file}")
    typer.echo("")
    typer.echo("Uruchomienie parsowania:")
    typer.echo(f"  helpdesk tickets parse {parsed_dir} \\")
    typer.echo(f"    $(sed 's/^/-t /' {ids_file} | tr '\\n' ' ')")


if __name__ == "__main__":
    cli()
