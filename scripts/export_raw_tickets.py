"""Export helpdesk tickets from a MariaDB container into data/raw/, one JSON file per ticket.

Do czego:
    Zdejmuje zgłoszenia jednego modułu ze zrzutu bazy `helpdesk` zaimportowanego do kontenera
    MariaDB i zapisuje je na dysk jako trwały punkt wyjścia dla dalszych etapów. Dzięki temu
    reszta projektu nie potrzebuje ani zrzutu SQL (37 MB, hasła, 29 tys. zgłoszeń spoza zakresu),
    ani działającego kontenera.

    Skrypt jest repo-level, nie należy do usługi `api` — nie importuje jej kodu, nie czyta
    `Settings` i nie odpytuje żadnego endpointu (patrz „Warstwa CLI" w CLAUDE.md).

Flow:
    1. `export` sprawdza, czy kontener odpowiada (`_run_query` na `SELECT 1`).
    2. Pobiera listę id zgłoszeń modułu (`_fetch_ticket_ids`).
    3. Dla każdego id pobiera pełny rekord z wątkiem komentarzy (`_fetch_ticket`) i zapisuje
       plik `zgloszenie-<id>.json` (`_write_ticket`).
    4. Na końcu porównuje liczbę plików i komentarzy z tym, co mówi baza (`_verify`).

Zasady:
    - **Raw znaczy raw** — HTML, encje, PII i martwe kolumny zostają dokładnie takie, jakie są
      w źródle. Strip, unescape i sklejanie wątku to robota adaptera z `ingest/`, nie eksportu.
    - **Bez filtrowania jakości** — wychodzą wszystkie zgłoszenia modułu, także te bez opisu
      i bez komentarzy. Filtr to decyzja etapu indeksacji i ma prawo się jeszcze zmienić;
      zabetonowany w artefakcie przestałby być widoczny.
    - **Kolumny z hasłami nie są czytane** — `konsultant.haslo`, `uzytkownik.haslo`
      i `skrzynka_email.password` nie pojawiają się w żadnym zapytaniu tego skryptu.
"""

import json
import pathlib
import subprocess

import typer

REPO_ROOT   = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "raw"

cli = typer.Typer(help="Eksport zgłoszeń helpdesku ze zrzutu bazy do data/raw/.")

# MariaDB buduje JSON sam — treści z HTML-em i znakami nowej linii nie przechodzą wtedy
# przez parsowanie TSV po stronie klienta, które by je rozjechało.
TICKET_QUERY = """
SELECT JSON_OBJECT(
  'zrodlo',     '{source_name}',
  'tabela',     'zgloszenie',
  'zgloszenie', JSON_OBJECT(
      'id',                 z.id,
      'created_at',         z.created_at,
      'updated_at',         z.updated_at,
      'status',             z.status,
      'kategoria',          kat.nazwa,
      'modul',              m.nazwa,
      'czego_dotyczy',      z.czego_dotyczy,
      'szczegolowy_opis',   z.szczegolowy_opis,
      'priorytet',          z.priorytet,
      'sposob_zgloszenia',  z.sposob_zgloszenia,
      'wersja_zgloszona',   z.wersja_zgloszona,
      'numer_mantis',       z.numer_mantis,
      'data_przyjecia',     z.data_przyjecia,
      'data_zamkniecia',    z.data_zamkniecia,
      'powod_zakonczenia',  z.powod_zakonczenia,
      'wykonane_czynnosci', z.wykonane_czynnosci,
      'przyczyna',          z.przyczyna,
      'rozwiazanieid',      z.rozwiazanieid,
      'ocena_rozwiazania',  z.ocena_rozwiazania,
      'instytucja',         i.nazwa,
      'osoba_kontakt',      z.osoba_kontakt,
      'email_kontakt',      z.email_kontakt,
      'telefon_kontakt',    z.telefon_kontakt
  ),
  'komentarze', (
      -- MariaDB nie pozwala odwołać się do z.id wewnątrz derived table, stąd ORDER BY
      -- wprost w JSON_ARRAYAGG; kolejność po id = kolejność wątku.
      SELECT JSON_ARRAYAGG(JSON_OBJECT(
          'id',         k.id,
          'typ',        k.typ,
          'autor_rola', CASE WHEN k.konsultantid IS NOT NULL THEN 'konsultant'
                             WHEN k.uzytkownikid  IS NOT NULL THEN 'klient'
                             ELSE 'brak' END,
          'created_at', k.created_at,
          'tresc',      k.tresc
      ) ORDER BY k.id)
      FROM komentarz k WHERE k.zgloszenieid = z.id
  )
)
FROM zgloszenie z
JOIN kategoria        kat ON kat.id = z.kategoriaid
JOIN modul_zgloszenia m   ON m.id   = z.modulid
JOIN uzytkownik       u   ON u.id   = z.uzytkownikid
JOIN instytucja       i   ON i.id   = u.instytucjaid
WHERE z.id = {ticket_id};
"""


def _run_query(
    container: str,  # e.g. "helpdesk-analiza"
    database:  str,  # e.g. "helpdesk"
    password:  str,  # e.g. "analiza"
    sql:       str,  # e.g. "SELECT COUNT(*) FROM zgloszenie;"
) -> str:
    """
    Description:
    Runs one SQL statement inside the MariaDB container and returns its raw stdout.

    Example args:
        container="helpdesk-analiza"
        database="helpdesk"
        password="analiza"
        sql="SELECT COUNT(*) FROM zgloszenie WHERE modulid = 116;"

    Example result:
        "1825"

    Raises:
        typer.Exit: when the container is unreachable or the query fails
    """
    # --- --raw wyłącza escapowanie klienta; JSON z MariaDB jest już poprawnie zaescapowany ---
    command = ["docker", "exec", container, "mariadb", "-uroot", f"-p{password}", database,
               "-N", "-B", "--raw", "-e", sql]
    result  = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        typer.echo(f"Zapytanie nie powiodło się: {result.stderr.strip()}", err=True)
        raise typer.Exit(code=1)
    # Klient MariaDB wypisuje ostrzeżenie o haśle w linii poleceń na stdout — odsiewamy je,
    # inaczej trafiłoby do JSON-a.
    kept = [line for line in result.stdout.splitlines() if not line.startswith("Warning")]
    return "\n".join(kept).strip()


def _fetch_ticket_ids(
    container: str,  # e.g. "helpdesk-analiza"
    database:  str,  # e.g. "helpdesk"
    password:  str,  # e.g. "analiza"
    module_id: int,  # e.g. 116 (Dokus)
) -> list[int]:
    """
    Description:
    Returns ids of all tickets of one module, in ascending order, without any quality filter.

    Example args:
        container="helpdesk-analiza"
        database="helpdesk"
        password="analiza"
        module_id=116

    Example result:
        [12045, 12088, 12134, ...]
    """
    rows = _run_query(container, database, password,
                      f"SELECT id FROM zgloszenie WHERE modulid = {module_id} ORDER BY id;")
    return [int(row) for row in rows.splitlines() if row]


def _fetch_ticket(
    container:   str,  # e.g. "helpdesk-analiza"
    database:    str,  # e.g. "helpdesk"
    password:    str,  # e.g. "analiza"
    ticket_id:   int,  # e.g. 34458
    source_name: str,  # e.g. "mysql_helpdesk_20260724-141140.sql"
) -> dict:
    """
    Description:
    Fetches one ticket together with its whole comment thread and returns it as a dict.

    Example args:
        container="helpdesk-analiza"
        database="helpdesk"
        password="analiza"
        ticket_id=34458
        source_name="mysql_helpdesk_20260724-141140.sql"

    Example result:
        {"zrodlo": "mysql_helpdesk_...", "tabela": "zgloszenie",
         "zgloszenie": {...}, "komentarze": [...]}
    """
    payload = _run_query(container, database, password,
                         TICKET_QUERY.format(source_name=source_name, ticket_id=ticket_id))
    return json.loads(payload)


def _write_ticket(
    out_dir: pathlib.Path,  # e.g. Path("/root/projects/dokus-helpdesk-ai/data/raw")
    ticket:  dict,          # e.g. {"zgloszenie": {"id": 34458, ...}, "komentarze": [...]}
) -> int:
    """
    Description:
    Writes one ticket to out_dir as zgloszenie-<id>.json and returns its comment count.

    Example args:
        out_dir=Path("data/raw")
        ticket={"zgloszenie": {"id": 34458, ...}, "komentarze": [...]}

    Example result:
        1
    """
    ticket_id = ticket["zgloszenie"]["id"]
    path      = out_dir / f"zgloszenie-{ticket_id}.json"
    path.write_text(json.dumps(ticket, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(ticket["komentarze"] or [])


def _verify(
    container:        str,            # e.g. "helpdesk-analiza"
    database:         str,            # e.g. "helpdesk"
    password:         str,            # e.g. "analiza"
    module_id:        int,            # e.g. 116
    out_dir:          pathlib.Path,   # e.g. Path("data/raw")
    written_comments: int,            # e.g. 4014
) -> bool:
    """
    Description:
    Compares the number of written files and comments against what the database reports.

    Example args:
        container="helpdesk-analiza"
        database="helpdesk"
        password="analiza"
        module_id=116
        out_dir=Path("data/raw")
        written_comments=4014

    Example result:
        True
    """
    expected = _run_query(container, database, password, f"""
        SELECT (SELECT COUNT(*) FROM zgloszenie WHERE modulid = {module_id}),
               (SELECT COUNT(*) FROM komentarz k JOIN zgloszenie z ON z.id = k.zgloszenieid
                WHERE z.modulid = {module_id});
    """)
    expected_tickets, expected_comments = (int(value) for value in expected.split("\t"))
    written_tickets = len(list(out_dir.glob("zgloszenie-*.json")))

    typer.echo(f"  zgłoszenia: {written_tickets} plików / {expected_tickets} w bazie")
    typer.echo(f"  komentarze: {written_comments} zapisanych / {expected_comments} w bazie")
    return written_tickets == expected_tickets and written_comments == expected_comments


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


DEFAULT_SOURCE = "mysql_helpdesk_20260724-141140.sql"

DEFAULT_CONTAINER = "helpdesk-analiza"

# Teksty pomocy w stałych, a nie w docstringach — inaczej Typer wstawi do `--help` opis pisany
# dla programisty (gotcha z CLAUDE.md → „Warstwa CLI").
HELP_COMMAND   = "Eksportuje wszystkie zgłoszenia modułu do katalogu docelowego."
HELP_MODULE    = "modulid zgłoszeń do eksportu (116 = Dokus)."
HELP_CONTAINER = "Nazwa kontenera z zaimportowanym zrzutem."
HELP_DATABASE  = "Nazwa bazy w kontenerze."
HELP_PASSWORD  = "Hasło roota do bazy w kontenerze."
HELP_SOURCE    = "Nazwa pliku zrzutu zapisywana w polu 'zrodlo'."
HELP_OUT_DIR   = "Katalog docelowy na pliki JSON."


@cli.command(help=HELP_COMMAND)
def export(
    module_id:   int          = typer.Option(116,               "--module-id", help=HELP_MODULE),
    container:   str          = typer.Option(DEFAULT_CONTAINER, "--container", help=HELP_CONTAINER),
    database:    str          = typer.Option("helpdesk",        "--database",  help=HELP_DATABASE),
    password:    str          = typer.Option("analiza",         "--password",  help=HELP_PASSWORD),
    source_name: str          = typer.Option(DEFAULT_SOURCE,    "--source",    help=HELP_SOURCE),
    out_dir:     pathlib.Path = typer.Option(DEFAULT_OUT,       "--out-dir",   help=HELP_OUT_DIR),
) -> None:
    """
    Description:
    Exports every ticket of one module into out_dir, one JSON file per ticket, then verifies counts.

    Example args:
        module_id=116
        container="helpdesk-analiza"
        out_dir=Path("data/raw")

    Example result:
        None (pliki na dysku + podsumowanie na stdout)

    Raises:
        typer.Exit: when the container is unreachable or the verification fails
    """
    _run_query(container, database, password, "SELECT 1;")          # fail-fast: kontener żyje?
    ticket_ids = _fetch_ticket_ids(container, database, password, module_id)
    if not ticket_ids:
        typer.echo(f"Moduł {module_id} nie ma żadnych zgłoszeń — nic do eksportu.", err=True)
        raise typer.Exit(code=1)

    out_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Eksport {len(ticket_ids)} zgłoszeń modułu {module_id} do {out_dir}")

    written_comments = 0
    for index, ticket_id in enumerate(ticket_ids, start=1):
        ticket            = _fetch_ticket(container, database, password, ticket_id, source_name)
        written_comments += _write_ticket(out_dir, ticket)
        if index % 100 == 0 or index == len(ticket_ids):
            typer.echo(f"  {index}/{len(ticket_ids)}")

    typer.echo("Kontrola liczb wobec bazy:")
    if not _verify(container, database, password, module_id, out_dir, written_comments):
        typer.echo("NIEZGODNOŚĆ — eksport niekompletny.", err=True)
        raise typer.Exit(code=1)
    typer.echo("Zgodne.")


if __name__ == "__main__":
    cli()
