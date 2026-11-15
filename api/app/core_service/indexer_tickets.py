"""
Description:
Indeksacja zgłoszeń: z korpusu (`data/unsafe/corpus/`) buduje oba indeksy, w których agent szuka
podobnych spraw — kolekcję kart w Qdrancie (szukanie po znaczeniu) i tabelę wątków w Postgresie
(szukanie po słowach i odczyt wątku). Nie woła LLM-a, tylko embedder i obie bazy, więc indeksy da
się skasować i odbudować jedną komendą.

    cards/*.json ─→ filtr jakości ─┬─ embedder (`problem` + `symptoms`) ────────────→ Qdrant
                                   └─ wątki kart przyjętych z anonymized/<numer>.txt → Postgres

| metoda      | kto woła                     | co robi                                            |
|-------------|------------------------------|----------------------------------------------------|
| `build()`   | `tickets index [<korpus>]`   | dokłada karty i wątki, nadpisując te same numery   |
| `rebuild()` | `tickets reindex [<korpus>]` | kasuje kolekcję i tabelę wątków, buduje je od zera |
| `add()`     | zamknięte zgłoszenie (p. 30) | dokłada jedną kartę i jej wątek                    |
| `remove()`  | zamknięte zgłoszenie (p. 30) | usuwa punkty i wiersze o podanych numerach         |

Przed — artefakt `data/unsafe/corpus/cards/33644.json`:

    {
      "ticket_id":         "33644",
      "date":              "2026-03-14",
      "component":         "ePUAP",
      "problem":           "Wysyłka przez ePUAP kończy się błędem komunikacji",
      "symptoms":          "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
      "error_codes":       ["ERR-4210"],
      "cause":             "Certyfikat bez uprawnienia AddDocumentToSign",
      "solution":          "Wygenerowano certyfikat z właściwym uprawnieniem.",
      "resolution":        "naprawione",
      "questions_summary": "brak",
      "resolution_vocabulary_version": 1
    }

Po — punkt w Qdrancie:

    {
      "id":      "df3b51f3-9eac-56f3-9f28-6253f23dd731",
      "vector":  {
        "problem": [0.0123, -0.0456, …],
        "sts":     [0.0987, -0.0654, …]
      },
      "payload": { …te same pola co w artefakcie… }
    }

Co się dzieje po drodze:

1. Filtr jakości odsiewa rekordy bez wiedzy (np. `solution` = „brak"); raport mówi, które
   odpadły i dlaczego.
2. Z `problem` + `symptoms` powstaje tekst do embeddingu. `solution` do wektora nie wchodzi —
   szukamy po podobieństwie problemu, nie rozwiązania.
3. Embedder liczy z tego tekstu dwa wektory (dziś po 768 liczb): `problem` w trybie passage,
   z nim porównywane jest zapytanie, i `sts` w trybie symetrycznym, którego dziś nikt nie czyta.
4. `id` punktu jest wyliczane z `ticket_id`, więc ponowna indeksacja nadpisuje punkt, zamiast
   go dublować.
5. Cały artefakt jedzie w payloadzie — z niego powstaje później propozycja odpowiedzi.
6. Wątek każdej karty przyjętej trafia do tabeli wątków jako wiersz: numer, data z karty, temat
   z linii „Temat:” i cały wątek po anonimizacji. Wątki kart odrzuconych do tabeli nie idą.

O czym pamiętać przy zmianach:

- Korpus bez katalogu `anonymized/` (np. katalog roboczy ponownego parsowania golden setu)
  buduje same karty, a tabela wątków zostaje bez zmian — raport mówi to polem `threads` równym
  `None`.
- Gdy `anonymized/` jest, każda karta musi mieć w nim swój wątek: brak to zepsuty korpus, więc
  przebieg odmawia, zanim cokolwiek zapisze albo skasuje.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.quality_report import QualityReport
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_model.tickets.tickets_index_report import TicketsIndexReport
from app.core_service.filter_ticket_quality import drop_rate_warning, filter_tickets
from app.db_postgres import TicketRow, TicketsTable
from app.db_qdrant import TicketPoint, TicketsCollection
from app.engine_anonymization import AnonymizedText
from app.engine_embedding import EmbeddingClient, EmbeddingConfigError

logger = logging.getLogger(__name__)

# Ile zgłoszeń idzie do embeddera w jednym wywołaniu. Cały korpus w jednym żądaniu uzależniłby
# przebieg od jednego timeoutu, a jedno zgłoszenie na żądanie traci większość czasu na podróże
# HTTP — model sam składa paczki wewnątrz i karmiony hurtem jest dużo szybszy.
EMBED_BATCH_SIZE = 32

# Ile numerów kart bez wątku wypisać w błędzie: dość, żeby znaleźć przyczynę, a nie całą listę.
MAX_LISTED_MISSING = 10


class TicketsIndexer:
    """
    Description:
    Buduje oba indeksy zgłoszeń z korpusu: kolekcję kart w Qdrancie i tabelę wątków w Postgresie.

    Do czego:
    Indeksy są pochodną, nigdy źródłem prawdy (zasada 8) — wszystko tutaj musi dać się odtworzyć
    z `cards/` i `anonymized/` korpusu jedną komendą i BEZ wołania LLM-a (zasada 7). Dlatego ten
    serwis czyta pliki z dysku i rozmawia wyłącznie z embedderem, Qdrantem i Postgresem. Oba
    indeksy trzyma jeden serwis, jak `DocsIndexer` przy dokumentacji, bo wątek trafia do tabeli
    tylko razem z kartą przyjętą przez filtr.

    Flow:
        1. `build()` wczytuje każdy `*.json` z `cards/` do `ParsedTicket` i sprawdza, czy
           `anonymized/` ma wątek każdej karty.
        2. Filtr jakości dzieli karty na zachowane i odrzucone, z powodem przy każdym odrzuceniu.
        3. Zachowane karty są embedowane paczkami — DWA RAZY, raz na named vector: `problem`
           w trybie passage (z nim porównywane jest zapytanie w runtime) i `sts` w trybie
           symetrycznym — i idą upsertem do kolekcji.
        4. Wątki zachowanych kart idą do tabeli wątków; raport niesie liczby, powody
           i ewentualne ostrzeżenia.
        5. `add()` i `remove()` robią to samo dla jednego zgłoszenia, bez czytania katalogu.
        6. `aclose()` zamyka połączenia, na których indekser stoi.

    Oba wektory budujemy celowo. Pomiar rozstrzygnął wyszukiwanie na korzyść `query→passage`,
    i na zapytaniach surowych (etap 3), i na sparsowanych (etap 4), więc wektora `sts` dziś nikt
    nie czyta. Zostaje mimo to: wraca razem ze zwijaniem trafień albo „podobnymi przypadkami",
    a usunięcie go teraz zamieniłoby ten powrót w pełny re-index (CLAUDE.md -> „Embeddingi").
    """

    def __init__(
        self,
        embedder: EmbeddingClient,    # np. EmbeddingClient(base_url="http://embedder:8000")
        tickets:  TicketsCollection,  # np. TicketsCollection(QdrantClient(…), "tickets", 768)
        threads:  TicketsTable,       # np. TicketsTable(PostgresClient(…))
    ):
        """
        Description:
        Spina indekser z embedderem, kolekcją zgłoszeń i tabelą wątków. Wszystkie są
        wstrzykiwane, a nie budowane tutaj: domena nigdy nie sięga po własne SDK ani URL
        (zasada 4). Wymiar wektorów zna kolekcja.

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            tickets=TicketsCollection(QdrantClient(base_url="http://qdrant:6333"), "tickets", 768)
            threads=TicketsTable(PostgresClient(…))

        Example result:
            TicketsIndexer gotowy do zbudowania kolekcji `tickets` i tabeli `tickets_text`
        """
        self._embedder = embedder
        self._tickets  = tickets
        self._threads  = threads

    async def build(
        self,
        corpus: TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
    ) -> TicketsIndexReport:
        """
        Description:
        Indeksuje korpus: karty do kolekcji, a wątki kart przyjętych do tabeli wątków, i zwraca,
        co zrobił. Czyta się jak lista kroków; szczegóły siedzą w prywatnych helperach niżej.

        Example args:
            corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))

        Example result:
            TicketsIndexReport(read=200, indexed=171, threads=171, filtered=QualityReport(…))

        Raises:
            NotADirectoryError: katalog kart nie istnieje albo nie jest katalogiem
            FileNotFoundError: `anonymized/` jest, ale nie ma w nim wątku którejś karty
            DbQdrantConfigError: kolekcja ma punkty innego modelu embeddera
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił zapis
            EmbeddingConfigError: embedder zmienił model w trakcie przebiegu
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        """
        tickets      = self._read(corpus.cards_dir)
        with_threads = self._has_threads(corpus, tickets)
        report       = filter_tickets(tickets)
        kept         = self._kept_tickets(tickets, report)

        await self._tickets.ensure()
        indexed = await self._upsert(kept)
        threads = await self._upsert_threads(corpus, kept) if with_threads else None

        # Same liczby: payloady i wątki niosą treść zgłoszeń, czyli dane klienta, którym miejsce
        # najwyżej na DEBUG (CLAUDE.md -> „Logi i obserwowalność").
        logger.info(
            "index build collection=%s read=%d indexed=%d dropped=%d threads=%s",
            self._tickets.name,
            len(tickets),
            indexed,
            len(report.dropped),
            threads,
        )

        warning = drop_rate_warning(report)

        build_report = TicketsIndexReport(
            read     = len(tickets),
            indexed  = indexed,
            threads  = threads,
            filtered = report,
            warnings = [warning] if warning else [],
        )

        return build_report

    async def rebuild(
        self,
        corpus: TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
    ) -> TicketsIndexReport:
        """
        Description:
        Kasuje kolekcję kart i, gdy korpus ma wątki, tabelę wątków, i buduje je od zera.
        Bezpieczne z konstrukcji, a nie dzięki ostrożności: indeksy da się odbudować z plików
        korpusu tą samą komendą (zasada 8), więc niszczona jest pochodna. Korpus bez
        `anonymized/` tabeli wątków nie rusza.

        Osobna metoda zamiast flagi w `build()`, bo obie różnią się tym, czym RYZYKUJĄ, a nie tym,
        jak działają — a CLI jedną z nich musi osłonić potwierdzeniem.

        Example args:
            corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))

        Example result:
            TicketsIndexReport(read=200, indexed=171, threads=171, …)

        Raises:
            NotADirectoryError: katalog kart nie istnieje albo nie jest katalogiem
            FileNotFoundError: w katalogu kart nie ma ani jednej karty albo `anonymized/` jest,
                ale nie ma w nim wątku którejś karty
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił polecenie
        """
        tickets = self._read(corpus.cards_dir)

        # Kasujemy dopiero wtedy, gdy jest z czego odbudować: zła ścieżka, katalog bez kart albo
        # karta bez wątku zostawiłyby po skasowaniu pusty albo niepełny indeks.
        if not tickets:
            raise FileNotFoundError(f"brak kart w katalogu, indeksy zostają: {corpus.cards_dir}")

        with_threads = self._has_threads(corpus, tickets)

        await self._tickets.drop()

        if with_threads:
            await self._threads.drop()

        return await self.build(corpus)

    async def add(
        self,
        ticket: ParsedTicket,    # np. ParsedTicket(ticket_id="41002", …) — przyjęta przez filtr
        thread: AnonymizedText,  # np. AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\n…")
    ) -> None:
        """
        Description:
        Dokłada jedną kartę, która już przeszła filtr jakości, do kolekcji, a jej wątek do tabeli
        wątków; kolekcję i tabelę zakłada, gdy ich nie ma. Punkt i wiersz tego samego zgłoszenia
        są nadpisywane. Tędy idzie zamknięte zgłoszenie (p. 30), bez czytania katalogu.

        Example args:
            ticket=ParsedTicket(ticket_id="41002", …)
            thread=AnonymizedText(text="ZGŁOSZENIE 41002 z 2026-11-11\nTemat: …")

        Example result:
            None

        Raises:
            ValueError: w wątku nie ma linii z tematem
            DbQdrantConfigError: kolekcja ma punkty innego modelu embeddera
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił zapis
            EmbeddingConfigError: embedder zmienił model w trakcie zapisu
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        """
        # Wiersz najpierw: wątek bez tematu ma odpaść, zanim cokolwiek trafi do któregoś indeksu.
        row = TicketRow.from_thread(ticket.ticket_id, ticket.date, thread.text)

        await self._tickets.ensure()
        await self._upsert([ticket])
        await self._threads.create()
        await self._threads.upsert([row])

    async def remove(
        self,
        ticket_ids: Sequence[str],  # np. ["41002"]
    ) -> None:
        """
        Description:
        Usuwa z kolekcji punkty, a z tabeli wątków wiersze zgłoszeń o podanych numerach; numer,
        którego nie ma, nie jest błędem. Kolekcję i tabelę zakłada, gdy ich nie ma. Tędy wypada
        zgłoszenie zamknięte ponownie, którego karta tym razem odpadła w filtrze.

        Example args:
            ticket_ids=["41002"]

        Example result:
            None

        Raises:
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił polecenie
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił polecenie
        """
        await self._tickets.ensure()
        await self._tickets.delete(ticket_ids)
        await self._threads.create()
        await self._threads.delete(ticket_ids)

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia embeddera, Qdranta i Postgresa. Sprzątający woła tylko to i nie musi
        wiedzieć, z czego indekser jest zbudowany.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._embedder.aclose()
        await self._tickets.aclose()
        await self._threads.aclose()

    def _read(
        self,
        directory: Path,  # np. Path("data/unsafe/corpus/cards")
    ) -> list[ParsedTicket]:
        """
        Description:
        Czyta każdy artefakt z katalogu, w kolejności posortowanej, żeby dwa przebiegi po tym
        samym korpusie dawały porównywalne raporty.

        Wadliwy artefakt przerywa przebieg, zamiast zostać pominięty: `helpdesk tickets validate`
        istnieje po to, żeby takie wyłapać wcześniej, a ciche zaindeksowanie 199 z 200 rekordów
        zostawiłoby lukę, której potem nikt nie zobaczy.

        Example args:
            directory=Path("data/unsafe/corpus/cards")

        Example result:
            [ParsedTicket(ticket_id="10012", …), …]

        Raises:
            NotADirectoryError: ścieżka nie istnieje albo nie jest katalogiem
            ValidationError: artefakt nie spełnia kontraktu
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"nie jest katalogiem: {directory}")

        tickets = [
            ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        ]

        return tickets

    def _kept_tickets(
        self,
        tickets: list[ParsedTicket],  # np. [ParsedTicket(ticket_id="10012", …)]
        report:  QualityReport,       # np. QualityReport(verdicts=[…])
    ) -> list[ParsedTicket]:
        """
        Description:
        Wybiera zgłoszenia zachowane przez filtr, w kolejności, w jakiej zostały wczytane.

        Raport niesie id zgłoszeń zamiast samych rekordów — celowo, żeby filtr dało się testować
        bez artefaktów — dlatego tutaj trzeba je z powrotem dopasować.

        Example args:
            tickets=[ParsedTicket(ticket_id="10012", …), ParsedTicket(ticket_id="19596", …)]
            report=QualityReport(verdicts=[…])

        Example result:
            [ParsedTicket(ticket_id="10012", …)]
        """
        kept_ids = {verdict.ticket_id for verdict in report.kept}

        return [ticket for ticket in tickets if ticket.ticket_id in kept_ids]

    def _has_threads(
        self,
        corpus:  TicketsCorpus,       # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
        tickets: list[ParsedTicket],  # np. [ParsedTicket(ticket_id="41002", …)] — wszystkie karty
    ) -> bool:
        """
        Description:
        Mówi, czy korpus ma wątki po anonimizacji, a gdy ma, sprawdza, czy każda karta ma w nim
        swój wątek. Sprawdza wszystkie karty, nie tylko przyjęte: karta bez wątku znaczy zepsuty
        korpus, niezależnie od tego, co powie o niej filtr.

        Example args:
            corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))
            tickets=[ParsedTicket(ticket_id="41002", …)]

        Example result:
            True

        Raises:
            FileNotFoundError: `anonymized/` jest, ale nie ma w nim wątku którejś karty
        """
        # --- korpus bez wątków (np. same nowe karty): same karty, tabela bez zmian ---
        if not corpus.anonymized_dir.is_dir():
            return False

        missing = [
            ticket.ticket_id
            for ticket in tickets
            if not self._thread_path(corpus, ticket.ticket_id).is_file()
        ]

        if missing:
            listed = ", ".join(missing[:MAX_LISTED_MISSING])

            raise FileNotFoundError(
                f"{len(missing)} kart bez wątku w {corpus.anonymized_dir} (np. {listed}); "
                "indeksy zostają"
            )

        return True

    def _thread_path(
        self,
        corpus:    TicketsCorpus,  # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
        ticket_id: str,            # np. "41002"
    ) -> Path:
        """
        Description:
        Ścieżka wątku zgłoszenia w korpusie: plik nazwany numerem zgłoszenia w `anonymized/`.

        Example args:
            corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))
            ticket_id="41002"

        Example result:
            Path("data/unsafe/corpus/anonymized/41002.txt")
        """
        return corpus.anonymized_dir / f"{ticket_id}.txt"

    async def _upsert_threads(
        self,
        corpus:  TicketsCorpus,       # np. TicketsCorpus(root=Path("data/unsafe/corpus"))
        tickets: list[ParsedTicket],  # np. [ParsedTicket(ticket_id="41002", …)] — przyjęte
    ) -> int:
        """
        Description:
        Zapisuje do tabeli wątków wątki podanych kart, zakładając tabelę, gdy jej nie ma, i oddaje,
        ile wierszy zapisano. Datę wiersza bierze z karty, temat z linii „Temat:” wątku.

        Example args:
            corpus=TicketsCorpus(root=Path("data/unsafe/corpus"))
            tickets=[ParsedTicket(ticket_id="41002", date=date(2026, 11, 11), …)]

        Example result:
            1

        Raises:
            ValueError: w wątku nie ma linii z tematem
            DbPostgresError: Postgres jest nieosiągalny albo odrzucił zapis
        """
        rows = [
            TicketRow.from_thread(
                ticket.ticket_id,
                ticket.date,
                self._thread_path(corpus, ticket.ticket_id).read_text(encoding="utf-8"),
            )
            for ticket in tickets
        ]

        await self._threads.create()
        await self._threads.upsert(rows)

        return len(rows)

    async def _upsert(
        self,
        tickets: list[ParsedTicket],  # np. [ParsedTicket(ticket_id="10012", …)]
    ) -> int:
        """
        Description:
        Embeduje zgłoszenia paczkami i zapisuje je jako punkty. Zwraca, ile zapisano.

        Każda paczka jest embedowana DWA RAZY — raz na named vector — bo oba żyją w różnych
        przestrzeniach wektorowych, a ich pomieszanie psuje wyszukiwanie po cichu (CLAUDE.md ->
        „Embeddingi"). Oba wywołania dostają te same teksty w tej samej kolejności, więc wyniki
        zipują się z powrotem na zgłoszenia, z których powstały; `strict=True` zamienia każdy
        rozjazd długości w błąd zamiast w po cichu obciętą paczkę.

        Example args:
            tickets=[ParsedTicket(ticket_id="10012", …)]

        Example result:
            1

        Raises:
            EmbeddingConfigError: wektory jednej paczki policzyły dwa różne modele
            EmbeddingError: embedder jest nieosiągalny albo zwrócił inną liczbę wektorów
            DbQdrantConfigError: kolekcja ma punkty innego modelu embeddera
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
        """
        written = 0

        for start in range(0, len(tickets), EMBED_BATCH_SIZE):
            batch = tickets[start : start + EMBED_BATCH_SIZE]
            # Ten sam tekst składa zapytanie w `find_tickets_vector` — obie strony przez
            # `build_embedding_text()`, żeby nie rozjechały się bezgłośnie.
            texts = [ticket.embedding_text() for ticket in batch]

            problem = await self._embedder.embed_passage(texts)
            sts     = await self._embedder.embed_sts(texts)

            # Punkt zapisuje jeden model dla obu wektorów, więc oba muszą pochodzić z tego samego.
            if problem.model != sts.model:
                raise EmbeddingConfigError(
                    f"embedder policzył wektory jednej paczki dwoma modelami ({problem.model}, "
                    f"{sts.model}) — zmienił model w trakcie przebiegu; uruchom indeksację od nowa"
                )

            points = [
                TicketPoint.from_ticket(
                    ticket          = ticket,
                    vector_problem  = problem_vector,
                    vector_sts      = sts_vector,
                    embedding_model = problem.model,
                )
                for ticket, problem_vector, sts_vector in zip(
                    batch, problem.vectors, sts.vectors, strict=True
                )
            ]

            written += await self._tickets.upsert(points)

        return written
