"""Buduje słownik szablonów kanału „Automat mailowy”: skróty fragmentów, które stoją w wielu
różnych wątkach tego kanału — stopek, zastrzeżeń poufności, klauzul RODO (CLAUDE.md -> p. 32).

Do czego:
    Normalizer maili (`api/app/core_service/normalizer_ticket_mail.py`) usuwa linie leżące
    w takim fragmencie także przy pierwszym wystąpieniu, zanim wątek trafi do anonimizatora.
    Skrypt czyta zgłoszenia kanału z `raw-db/` korpusu i zapisuje `slownik.json` do katalogu
    słownika maili, obok `nazwy.json`, którego nie rusza:

    python scripts/build_mail_dictionary.py build data/unsafe/corpus data/unsafe/mail

    Słownik zmyślony, do testów, powstaje z kilku zmyślonych wątków leżących obok niego,
    z niższym progiem, bo wątków jest mało:

    python scripts/build_mail_dictionary.py build data/safe/mail data/safe/mail --min-threads 2

Jak powstaje słownik (`build_templates`):
    1. Z każdego wątku kanału bierze treść wiadomości w kształcie, który czyści normalizer
       (`message_texts()`: opis i komentarze bez odwołań do obrazków).
    2. Zbiera skróty wszystkich ciągów `run_words` kolejnych słów wątku, każdy raz na wątek.
    3. Liczy, w ilu wątkach stoi każdy skrót.
    4. Do słownika wchodzą skróty z co najmniej `min_threads` wątków, posortowane.

O czym pamiętać przy zmianach:
    - Wchodzą wątki kanału bez względu na status: szablon to cecha kanału, nie sprawy.
    - Słownik zapisuje `run_words`, z którym go policzono, a normalizer bierze długość ciągu
      stąd: skrót znaczy coś tylko przy tej długości.
    - Słownik opisuje korpus z dnia budowy; po przyroście korpusu buduje się go od nowa.
    - Korpus bez wątków kanału to błąd: pusty słownik wyglądałby jak kanał bez szablonów.
"""

import datetime
import pathlib
import sys
from collections import Counter
from collections.abc import Sequence

import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.core_model.dicts.mail_templates import MailTemplates  # noqa: E402  (po sys.path)
from app.core_model.tickets.raw_ticket import RawTicket  # noqa: E402
from app.core_model.tickets.tickets_corpus import TicketsCorpus  # noqa: E402
from app.core_service.loader_mail_dictionary import TEMPLATES_FILE  # noqa: E402
from app.core_service.normalizer_ticket_mail import message_texts  # noqa: E402
from app.core_service.parser_ticket_raw import MAIL_CATEGORY, load_raw_ticket  # noqa: E402
from app.core_util.repetition import run_digests  # noqa: E402

# Długość fragmentu w słowach: krótszy wycinał zwroty z nowych wiadomości („Dzień dobry,
# w nawiązaniu do…”), a dłuższy nie dawał lepszego czyszczenia (sondy na 136 wątkach, p. 32).
RUN_WORDS_DEFAULT = 12

# W ilu różnych wątkach musi stać fragment, żeby był szablonem: stopki dostawcy i urzędów stoją
# w dziesiątkach wątków, a zdanie jednej sprawy — w kilku.
MIN_THREADS_DEFAULT = 10

cli = typer.Typer(help="Słownik szablonów kanału „Automat mailowy”.")


@cli.callback()
def main() -> None:
    """
    Description:
    Grupa komend skryptu: `build`.

    Example args:
        (brak)

    Example result:
        None
    """


def mail_tickets(corpus: TicketsCorpus) -> list[RawTicket]:   # np. TicketsCorpus(root=…)
    """
    Description:
    Czyta z `raw-db/` korpusu zgłoszenia kanału „Automat mailowy”, po numerze.

    Example args:
        corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))

    Example result:
        [RawTicket(ticket_id="33605", category="Automat mailowy", …), …]
    """
    paths   = sorted(corpus.raw_db_dir.glob("zgloszenie-*.json"))
    tickets = [ticket for ticket in map(load_raw_ticket, paths) if ticket.category == MAIL_CATEGORY]

    return sorted(tickets, key=lambda ticket: int(ticket.ticket_id))


def build_templates(
    tickets:     Sequence[RawTicket],  # np. [RawTicket(ticket_id="33605", …), …]
    run_words:   int,                  # np. 12
    min_threads: int,                  # np. 10
    source:      str,                  # np. "data/unsafe/corpus"
    built_on:    datetime.date,        # np. date(2026, 11, 20)
) -> MailTemplates:
    """
    Description:
    Liczy słownik szablonów: skróty ciągów `run_words` słów, które stoją w co najmniej
    `min_threads` różnych wątkach.

    Example args:
        tickets=[RawTicket(ticket_id="33605", …), …]
        run_words=12
        min_threads=10
        source="data/unsafe/corpus"
        built_on=date(2026, 11, 20)

    Example result:
        MailTemplates(threads=139, run_words=12, min_threads=10, digests=["0060…", …], …)
    """
    in_threads: Counter[str] = Counter()

    # Zbiór na wątek: fragment powtórzony w jednym wątku (druga kopia maila, cytaty) liczy się
    # raz, bo szablon to fragment wspólny RÓŻNYM wątkom.
    for ticket in tickets:
        thread: set[str] = set()
        for text in message_texts(ticket):
            thread |= run_digests(text, run_words)
        in_threads.update(thread)

    digests   = sorted(digest for digest, count in in_threads.items() if count >= min_threads)
    templates = MailTemplates(
        built_on    = built_on,
        source      = source,
        threads     = len(tickets),
        run_words   = run_words,
        min_threads = min_threads,
        digests     = digests,
    )

    return templates


@cli.command("build", help="Buduje słownik szablonów z wątków kanału w korpusie.")
def build(
    corpus_dir:  pathlib.Path = typer.Argument(help="Katalog korpusu z podkatalogiem raw-db/."),
    out_dir:     pathlib.Path = typer.Argument(help="Katalog słownika maili."),
    min_threads: int          = typer.Option(MIN_THREADS_DEFAULT, min=1, help="Od ilu wątków."),
    run_words:   int          = typer.Option(RUN_WORDS_DEFAULT, min=1, help="Słów we fragmencie."),
) -> None:
    """
    Description:
    Buduje słownik szablonów z wątków kanału w `raw-db/` korpusu i zapisuje go jako
    `slownik.json` w katalogu słownika maili, zastępując poprzedni. Kończy się kodem 1, gdy
    w korpusie nie ma ani jednego wątku kanału; wtedy niczego nie zapisuje.

    Example args:
        corpus_dir=Path("data/unsafe/corpus")
        out_dir=Path("data/unsafe/mail")
        min_threads=10
        run_words=12

    Example result:
        None — `data/unsafe/mail/slownik.json`, podsumowanie na wyjściu

    Raises:
        typer.Exit: code 1, gdy w korpusie nie ma wątków kanału „Automat mailowy”
    """
    tickets = mail_tickets(TicketsCorpus(root=corpus_dir))

    if not tickets:
        typer.echo(f"W {corpus_dir}/raw-db/ nie ma zgłoszeń kanału „{MAIL_CATEGORY}”.", err=True)
        raise typer.Exit(code=1)

    today     = datetime.date.today()
    templates = build_templates(tickets, run_words, min_threads, str(corpus_dir), today)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / TEMPLATES_FILE
    path.write_text(templates.model_dump_json(indent=2) + "\n", encoding="utf-8")

    typer.echo(f"Wątki kanału: {templates.threads}, szablony: {len(templates.digests)} "
               f"(fragmenty {run_words} słów z co najmniej {min_threads} wątków) → {path}")


if __name__ == "__main__":
    cli()
