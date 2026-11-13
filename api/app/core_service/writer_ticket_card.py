"""
Description:
Zapisuje w korpusie kartę zgłoszenia razem z wątkiem, z którego powstała: wątek po anonimizacji
do `anonymized/<numer>.txt`, kartę do `cards/<numer>.json`. Wołają go obie drogi, którymi karta
trafia do korpusu: trasa zamknięcia zgłoszenia (`ClosedTicketIndexer`, p. 30) i masowy import
(`TicketsImporter`, p. 31).

Przed — wątek i karta zgłoszenia 41002 z grafu `parse_ticket`:

    AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\\nTemat: Brak przesyłek…")
    ParsedTicket(ticket_id="41002", useful=True, …)

Po — dwa pliki w korpusie i odpowiedź, czy karta tego numeru już tam leżała:

    data/unsafe/corpus/anonymized/41002.txt
    data/unsafe/corpus/cards/41002.json
    False

O czym pamiętać przy zmianach:

- Karta idzie ostatnia, więc nigdy nie leży bez swojego wątku: indeksacja korpusu z `anonymized/`
  odmawia, gdy któraś karta nie ma wątku, a przerwany zapis zostawia co najwyżej wątek bez karty,
  który następny zapis nadpisze.
- Funkcja nadpisuje, co zastanie. Czy wolno nadpisać kartę, rozstrzyga wołający: trasa nadpisuje
  przy ponownym zamknięciu, import pomija zgłoszenia, które kartę już mają.
"""

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.engine_anonymization import AnonymizedText


def write_card_with_thread(
    corpus: TicketsCorpus,   # np. TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
    thread: AnonymizedText,  # np. AnonymizedText(text="ZGŁOSZENIE 41002…")
    card:   ParsedTicket,    # np. ParsedTicket(ticket_id="41002", …)
) -> bool:
    """
    Description:
    Zapisuje wątek po anonimizacji i kartę pod numerem karty, kartę na końcu, i mówi, czy karta
    tego numeru leżała już w korpusie. Katalogi zakłada, gdy ich nie ma.

    Example args:
        corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
        thread=AnonymizedText(text="ZGŁOSZENIE 41002…")
        card=ParsedTicket(ticket_id="41002", …)

    Example result:
        False — karty 41002 wcześniej nie było
    """
    card_path   = corpus.cards_dir / f"{card.ticket_id}.json"
    thread_path = corpus.anonymized_dir / f"{card.ticket_id}.txt"
    replaced    = card_path.exists()

    # Kolejność wpisów to kolejność zapisu: karta ostatnia, żeby nie leżała bez wątku.
    files = {
        thread_path: thread.text,
        card_path:   card.model_dump_json(indent=2) + "\n",
    }

    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return replaced
