"""Select a stratified batch of tickets from data/raw/ and render it as plain text for parsing.

Do czego:
    Przygotowuje materiał do ręcznego parsowania zgłoszeń w czacie: dobiera próbkę warstwowo
    (proporcjonalnie do kategorii), pomija zgłoszenia już sparsowane i zapisuje je jako czysty
    tekst w porcjach. Dzięki temu parsujący czyta 15 zgłoszeń bez HTML-a i metadanych zamiast
    surowych JSON-ów, co kilkukrotnie zmniejsza zużycie kontekstu.

    Skrypt jest repo-level, nie należy do usługi `api` (patrz „Warstwa CLI" w CLAUDE.md).

Flow:
    1. `prepare` wczytuje `data/raw/`, odsiewa zgłoszenia już obecne w `data/parsed/`
       i te, które nie przechodzą filtru jakości (`_passes_quality`).
    2. Grupuje pozostałe po kategorii i dobiera próbkę proporcjonalnie (`_pick_stratified`).
    3. Renderuje każde zgłoszenie jako tekst (`_render_ticket`) i zapisuje w porcjach.
    4. Wypisuje listę wybranych identyfikatorów — dobór ma być odtwarzalny i sprawdzalny.

Zasady:
    - **Filtr jakości liczony na tekście po stripie**, nie na surowym HTML-u. Różnica jest realna:
      na całym module 1496 zgłoszeń przechodzi próg liczony na HTML-u, a 1477 na samym tekście —
      19 przechodzi wyłącznie dzięki tagom i encjom.
    - **Dobór deterministyczny** (równomierny skok po posortowanych id, bez losowania), żeby
      dwa uruchomienia z tymi samymi parametrami dały tę samą próbkę.
"""

import html
import json
import pathlib
import re
from collections import defaultdict

import typer

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_PAR = REPO_ROOT / "data" / "parsed"
DEFAULT_OUT = REPO_ROOT / "data" / "batch"

MIN_CHARS   = 50   # próg treści dla opisu i dla komentarza, liczony po stripie
ROLE_NAME   = {"konsultant": "KONSULTANT", "klient": "KLIENT", "brak": "AUTOR NIEZNANY"}

cli = typer.Typer(help="Dobór i przygotowanie porcji zgłoszeń do ręcznego parsowania.")

HELP_COMMAND = "Dobiera próbkę zgłoszeń i zapisuje ją jako porcje tekstu."
HELP_COUNT   = "Ile zgłoszeń dobrać."
HELP_CHUNK   = "Ile zgłoszeń w jednej porcji (jeden plik = jedno czytanie)."
HELP_RAW     = "Katalog ze zgłoszeniami źródłowymi (JSON per zgłoszenie)."
HELP_PARSED  = "Katalog ze sparsowanymi zgłoszeniami — te zostaną pominięte."
HELP_OUT     = "Katalog docelowy na porcje tekstu."


def _strip_html(markup: str) -> str:  # e.g. "<p>Dzie&#324; dobry</p>"
    """
    Description:
    Turns source HTML into readable plain text, preserving line structure of paragraphs and lists.

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
    Tells whether a ticket has enough substance to be worth an LLM call.

    Example args:
        ticket={"zgloszenie": {"status": "rozwiazany", "szczegolowy_opis": "<p>...</p>"},
                "komentarze": [{"tresc": "<p>...</p>"}]}

    Example result:
        True
    """
    z = ticket["zgloszenie"]
    if z["status"] not in ("rozwiazany", "zamkniety"):
        return False
    if len(_strip_html(z["szczegolowy_opis"])) <= MIN_CHARS:
        return False
    return any(len(_strip_html(k["tresc"])) > MIN_CHARS for k in ticket["komentarze"] or [])


def _pick_stratified(
    by_category: dict,  # e.g. {"Błąd": [5629, 6378], "Usterka": [6409]}
    count:       int,   # e.g. 200
) -> list[int]:
    """
    Description:
    Picks ids proportionally to category size, spreading the choice evenly over sorted ids.

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


def _render_ticket(ticket: dict) -> str:  # e.g. {"zgloszenie": {...}, "komentarze": [...]}
    """
    Description:
    Renders one ticket and its whole comment thread as plain text with a short header.

    Example args:
        ticket={"zgloszenie": {"id": 34458, "kategoria": "Błąd", ...}, "komentarze": [...]}

    Example result:
        "===== ZGLOSZENIE 34458 =====\\nDATA: 2026-07-22 | KATEGORIA: Błąd | ..."
    """
    z     = ticket["zgloszenie"]
    lines = [
        f"===== ZGLOSZENIE {z['id']} =====",
        f"DATA: {z['created_at'][:10]} | KATEGORIA: {z['kategoria']} | STATUS: {z['status']}",
        f"POWOD_ZAKONCZENIA: {z['powod_zakonczenia']}",
        f"TEMAT: {z['czego_dotyczy']}",
        "OPIS:", _strip_html(z["szczegolowy_opis"]),
    ]
    for comment in ticket["komentarze"] or []:
        lines += [f"--- {ROLE_NAME[comment['autor_rola']]} (typ={comment['typ']}) ---",
                  _strip_html(comment["tresc"])]
    return "\n".join(lines)


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
def prepare(
    count:      int          = typer.Option(200,         "--count",      help=HELP_COUNT),
    chunk_size: int          = typer.Option(15,          "--chunk-size", help=HELP_CHUNK),
    raw_dir:    pathlib.Path = typer.Option(DEFAULT_RAW, "--raw-dir",    help=HELP_RAW),
    parsed_dir: pathlib.Path = typer.Option(DEFAULT_PAR, "--parsed-dir", help=HELP_PARSED),
    out_dir:    pathlib.Path = typer.Option(DEFAULT_OUT, "--out-dir",    help=HELP_OUT),
) -> None:
    """
    Description:
    Selects a fresh batch of not-yet-parsed tickets and writes it to out_dir as text chunks.

    Example args:
        count=200
        chunk_size=15
        out_dir=Path("data/batch")

    Example result:
        None (pliki chunk-NN.txt na dysku + lista wybranych id na stdout)

    Raises:
        typer.Exit: when there is nothing left to parse
    """
    already     = {int(p.stem.split("-")[1]) for p in parsed_dir.glob("zgloszenie-*.json")}
    by_category = defaultdict(list)

    for path in sorted(raw_dir.glob("zgloszenie-*.json")):
        ticket = json.loads(path.read_text(encoding="utf-8"))
        if ticket["zgloszenie"]["id"] in already or not _passes_quality(ticket):
            continue
        by_category[ticket["zgloszenie"]["kategoria"]].append(ticket["zgloszenie"]["id"])

    if not by_category:
        typer.echo("Brak zgłoszeń do sparsowania — wszystko już przerobione.", err=True)
        raise typer.Exit(code=1)

    picked = _pick_stratified(by_category, count)

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("chunk-*.txt"):
        stale.unlink()

    for chunk_no, start in enumerate(range(0, len(picked), chunk_size), start=1):
        blocks = []
        for ticket_id in picked[start:start + chunk_size]:
            raw = (raw_dir / f"zgloszenie-{ticket_id}.json").read_text(encoding="utf-8")
            blocks.append(_render_ticket(json.loads(raw)))
        (out_dir / f"chunk-{chunk_no:02d}.txt").write_text("\n\n".join(blocks), encoding="utf-8")

    chunks = list(out_dir.glob("chunk-*.txt"))
    chars  = sum(len(p.read_text(encoding="utf-8")) for p in chunks)
    typer.echo(f"Pominięto już sparsowanych: {len(already)}")
    typer.echo(f"Dostępnych do parsowania:   {sum(len(v) for v in by_category.values())}")
    typer.echo(f"Wybrano: {len(picked)} w {len(chunks)} porcjach, {chars} znakow")
    typer.echo(f"Katalog: {out_dir}")
    typer.echo("Identyfikatory: " + ",".join(str(i) for i in picked))


if __name__ == "__main__":
    cli()
