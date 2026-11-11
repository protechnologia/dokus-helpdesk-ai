"""
Description:
Dokłada do korpusu jedno zamknięte zgłoszenie (p. 30). Najpierw zapisuje na dysku surowe
zgłoszenie, wątek po anonimizacji i kartę, potem przepuszcza kartę przez filtr jakości. Kartę
przyjętą dokłada do Qdranta, a jej wątek do tabeli wątków w Postgresie; kartę odrzuconą usuwa
z obu, bo zgłoszenie zamknięte ponownie mogło tam stać z poprzednią kartą. Woła go trasa
zamknięcia zgłoszenia, po bramce i grafie karty.

Przed — zgłoszenie 41002 po bramce i grafie karty:

    RawTicket(ticket_id="41002", body="Od wczoraj nie przychodzą przesyłki…", …)
    AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\\nTemat: Brak przesyłek…")
    ParsedTicket(ticket_id="41002", useful=True, …)

Po — pliki w korpusie i raport:

    data/unsafe/corpus/raw-route/41002.json     surowe zgłoszenie (`RawTicket`)
    data/unsafe/corpus/anonymized/41002.txt     wątek, który dostał model
    data/unsafe/corpus/cards/41002.json         karta
    ClosedTicketReport(ticket_id="41002", replaced=False, indexed=True, dropped_by=[])

Co się dzieje po drodze:

1. Trzy pliki trafiają na dysk, karta ostatnia, więc karta nie leży nigdy bez swojego wątku.
   Zgłoszenie zamknięte ponownie nadpisuje wszystkie trzy.
2. Filtr jakości ocenia kartę (`evaluate_ticket()`).
3. Karta przyjęta: punkt w Qdrancie (`TicketsIndexer.add()`) i wiersz w tabeli wątków.
4. Karta odrzucona: punkt i wiersz tego numeru są usuwane, jeśli były.

O czym pamiętać przy zmianach:

- Pliki idą pierwsze, bo są źródłem prawdy (zasada 8): gdy Qdrant albo Postgres padnie w kroku 3
  albo 4, pliki zostają, a indeksy odbudowuje `helpdesk tickets reindex`.
- Nadpisywanie plików przy ponownym zamknięciu to jedyny wyjątek od zakazu nadpisywania
  w korpusie (decyzja 2026-11-11): nowszy wątek jest pełniejszy, a karta kosztuje grosze.
- Wątek trafia do tabeli tylko razem z kartą przyjętą przez filtr (decyzja 2026-11-11).
- W logu stoją tylko numery i liczby: zgłoszenie z trasy to dane klienta.
"""

import logging

from app.core_model.tickets.closed_ticket_report import ClosedTicketReport
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.filter_ticket_quality import evaluate_ticket
from app.core_service.indexer_tickets import TicketsIndexer
from app.db_postgres import TicketRow, TicketsTable
from app.engine_anonymization import AnonymizedText

logger = logging.getLogger(__name__)


class ClosedTicketIndexer:
    """
    Description:
    Zapisuje zamknięte zgłoszenie do korpusu i uzgadnia z nim indeksy: Qdranta z kartami i tabelę
    wątków w Postgresie.

    Do czego:
    Noga 2 karmi nogę 1: zgłoszenie zamknięte z pozytywnym werdyktem bramki staje się materiałem
    wyszukiwania bez czekania na kolejny masowy import. Serwis nie woła bramki ani grafu karty —
    dostaje gotowe zgłoszenie, wątek i kartę od trasy, więc da się go sprawdzić bez modelu.

    Flow:
        1. `add()` sprawdza, że trzy części dotyczą jednego zgłoszenia.
        2. `_write()` zapisuje pliki i mówi, czy karta tego numeru już była w korpusie.
        3. Filtr jakości ocenia kartę.
        4. `_index()` dokłada kartę przyjętą do obu indeksów, `_remove()` usuwa odrzuconą.
        5. `aclose()` zamyka połączenia, na których serwis stoi.
    """

    def __init__(
        self,
        corpus:  TicketsCorpus,   # np. Settings().tickets_corpus()
        cards:   TicketsIndexer,  # np. build_tickets_indexer(Settings())
        threads: TicketsTable,    # np. TicketsTable(PostgresClient(…))
    ):
        """
        Description:
        Spina serwis z katalogiem korpusu, indekserem kart i tabelą wątków. Wszystkie trzy są
        wstrzykiwane: serwis nie składa klientów sam (zasada 4).

        Example args:
            corpus=TicketsCorpus(root=Path("/code/data/unsafe/corpus"))
            cards=TicketsIndexer(embedder=EmbeddingClient(…), tickets=TicketsCollection(…))
            threads=TicketsTable(PostgresClient(…))

        Example result:
            ClosedTicketIndexer piszący do `/code/data/unsafe/corpus` i obu indeksów
        """
        self._corpus  = corpus
        self._cards   = cards
        self._threads = threads

    async def add(
        self,
        raw:    RawTicket,       # np. RawTicket(ticket_id="41002", body="Od wczoraj…", …)
        thread: AnonymizedText,  # np. AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\n…")
        card:   ParsedTicket,    # np. ParsedTicket(ticket_id="41002", useful=True, …)
    ) -> ClosedTicketReport:
        """
        Description:
        Dokłada zamknięte zgłoszenie do korpusu i oddaje, co z nim zrobiono: czy zastąpiło
        poprzednią kartę, czy karta jest w indeksie i które reguły filtra ją odrzuciły.

        Example args:
            raw=RawTicket(ticket_id="41002", …)
            thread=AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\\nTemat: …")
            card=ParsedTicket(ticket_id="41002", useful=True, …)

        Example result:
            ClosedTicketReport(ticket_id="41002", replaced=False, indexed=True, dropped_by=[])

        Raises:
            ValueError: zgłoszenie i karta mają różne numery albo w wątku nie ma linii z tematem
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił polecenie
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        """
        # Pliki trzech etapów jednego zgłoszenia leżą pod jednym numerem: pomyłka u wołającego
        # podpięłaby kartę pod cudzy wątek, więc odmawiamy przed zapisem czegokolwiek.
        if raw.ticket_id != card.ticket_id:
            raise ValueError(f"zgłoszenie {raw.ticket_id} i karta {card.ticket_id} to różne numery")

        replaced = self._write(raw, thread, card)
        verdict  = evaluate_ticket(card)

        if verdict.keep:
            await self._index(card, thread)
        else:
            await self._remove(card.ticket_id)

        logger.info(
            "closed ticket ticket_id=%s replaced=%s indexed=%s dropped_by=%s",
            card.ticket_id,
            replaced,
            verdict.keep,
            ",".join(verdict.reasons),
        )

        report = ClosedTicketReport(
            ticket_id  = card.ticket_id,
            replaced   = replaced,
            indexed    = verdict.keep,
            dropped_by = verdict.hits,
        )

        return report

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia indeksera kart i tabeli wątków. Sprzątający woła tylko to.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._cards.aclose()
        await self._threads.aclose()

    def _write(
        self,
        raw:    RawTicket,       # np. RawTicket(ticket_id="41002", …)
        thread: AnonymizedText,  # np. AnonymizedText(text="ZGŁOSZENIE 41002…")
        card:   ParsedTicket,    # np. ParsedTicket(ticket_id="41002", …)
    ) -> bool:
        """
        Description:
        Zapisuje surowe zgłoszenie, wątek i kartę, kartę na końcu, i mówi, czy karta tego numeru
        leżała już w korpusie. Katalogi zakłada, gdy ich nie ma.

        Example args:
            raw=RawTicket(ticket_id="41002", …)
            thread=AnonymizedText(text="ZGŁOSZENIE 41002…")
            card=ParsedTicket(ticket_id="41002", …)

        Example result:
            False — karty 41002 wcześniej nie było
        """
        ticket_id = card.ticket_id
        card_path = self._corpus.cards_dir / f"{ticket_id}.json"
        replaced  = card_path.exists()

        # Kolejność wpisów to kolejność zapisu: karta ostatnia, żeby nie leżała bez wątku.
        raw_path    = self._corpus.raw_route_dir / f"{ticket_id}.json"
        thread_path = self._corpus.anonymized_dir / f"{ticket_id}.txt"
        files       = {
            raw_path:    raw.model_dump_json(indent=2) + "\n",
            thread_path: thread.text,
            card_path:   card.model_dump_json(indent=2) + "\n",
        }

        for path, text in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        return replaced

    async def _index(
        self,
        card:   ParsedTicket,    # np. ParsedTicket(ticket_id="41002", …)
        thread: AnonymizedText,  # np. AnonymizedText(text="ZGŁOSZENIE 41002…")
    ) -> None:
        """
        Description:
        Dokłada kartę przyjętą do Qdranta, a jej wątek do tabeli wątków; tabelę zakłada, gdy jej
        nie ma. Punkt i wiersz tego samego numeru są nadpisywane.

        Example args:
            card=ParsedTicket(ticket_id="41002", …)
            thread=AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\\nTemat: …")

        Example result:
            None

        Raises:
            ValueError: w wątku nie ma linii z tematem
        """
        row = TicketRow.from_thread(card.ticket_id, card.date, thread.text)

        await self._cards.add([card])
        await self._threads.create()
        await self._threads.upsert([row])

    async def _remove(
        self,
        ticket_id: str,  # np. "41002"
    ) -> None:
        """
        Description:
        Usuwa z obu indeksów punkt i wiersz zgłoszenia, którego karta odpadła w filtrze; gdy ich
        nie było, nic się nie dzieje. Pliki zostają w korpusie: filtr może się zmienić,
        a przebudowa indeksu oceni kartę od nowa.

        Example args:
            ticket_id="41002"

        Example result:
            None
        """
        await self._cards.remove([ticket_id])
        await self._threads.create()
        await self._threads.delete([ticket_id])
