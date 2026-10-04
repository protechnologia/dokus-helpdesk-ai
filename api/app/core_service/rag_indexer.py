"""
Description:
Indeksacja: z katalogu sparsowanych zgłoszeń (`data/parsed/`) buduje kolekcję Qdranta, po której
w runtime szuka się podobnych zgłoszeń. Nie woła LLM-a — tylko embedder i Qdranta — więc indeks
da się skasować i odbudować jedną komendą.

    data/parsed/*.json → filtr jakości → embedder (`problem` + `symptoms`) → Qdrant

| metoda      | komenda                 | co robi                                          |
|-------------|-------------------------|--------------------------------------------------|
| `build()`   | `rag index <katalog>`   | dokłada artefakty, nadpisując punkty tych samych |
| `rebuild()` | `rag reindex <katalog>` | kasuje kolekcję i buduje od zera                 |

Przed — artefakt `data/parsed/33644.json`:

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
"""

import logging
from pathlib import Path

from app.core_model.filter_quality_report import QualityReport
from app.core_model.rag_index_report import IndexBuildReport
from app.core_model.ticket_parsed import ParsedTicket
from app.core_service.filter_ticket_quality import drop_rate_warning, filter_tickets
from app.db_qdrant import QdrantClient, TicketPoint
from app.engine_embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# Ile zgłoszeń idzie do embeddera w jednym wywołaniu. Cały korpus w jednym żądaniu uzależniłby
# przebieg od jednego timeoutu, a jedno zgłoszenie na żądanie traci większość czasu na podróże
# HTTP — model sam składa paczki wewnątrz i karmiony hurtem jest dużo szybszy.
EMBED_BATCH_SIZE = 32


class TicketIndexer:
    """
    Description:
    Buduje indeks Qdranta ze sparsowanych artefaktów: odczyt, filtr, embedding, upsert.

    Do czego:
    Indeks jest pochodną, nigdy źródłem prawdy (zasada 8) — wszystko tutaj musi dać się odtworzyć
    z `data/parsed/` jedną komendą i BEZ wołania LLM-a (zasada 7). Dlatego ten serwis czyta
    artefakty z dysku i rozmawia wyłącznie z embedderem i Qdrantem.

    Flow:
        1. `build()` wczytuje każdy `*.json` z katalogu do `ParsedTicket`.
        2. Filtr jakości dzieli je na zachowane i odrzucone, z powodem przy każdym odrzuceniu.
        3. Zachowane zgłoszenia są embedowane paczkami — DWA RAZY, raz na named vector: `problem`
           w trybie passage (z nim porównywane jest zapytanie w runtime) i `sts` w trybie
           symetrycznym.
        4. Punkty idą upsertem; raport niesie liczby, powody i ewentualne ostrzeżenia.

    Oba wektory budujemy celowo. Pomiar rozstrzygnął wyszukiwanie na korzyść `query→passage`,
    i na zapytaniach surowych (etap 3), i na sparsowanych (etap 4), więc wektora `sts` dziś nikt
    nie czyta. Zostaje mimo to: wraca razem ze zwijaniem trafień albo „podobnymi przypadkami",
    a usunięcie go teraz zamieniłoby ten powrót w pełny re-index (CLAUDE.md -> „Embeddingi").
    """

    def __init__(
        self,
        embedder:    EmbeddingClient,  # np. EmbeddingClient(base_url="http://embedder:8000")
        qdrant:      QdrantClient,     # np. QdrantClient(base_url="http://qdrant:6333", …)
        vector_size: int,              # np. 768 — musi zgadzać się z EMBEDDING_VECTOR_SIZE
    ):
        """
        Description:
        Spina indekser z dwiema usługami, których potrzebuje. Oba klienty są wstrzykiwane, a nie
        budowane tutaj: domena nigdy nie sięga po własne SDK ani URL (zasada 4).

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            qdrant=QdrantClient(base_url="http://qdrant:6333", collection="tickets")
            vector_size=768

        Example result:
            TicketIndexer gotowy do zbudowania kolekcji `tickets`
        """
        self._embedder    = embedder
        self._qdrant      = qdrant
        self._vector_size = vector_size

    async def build(
        self,
        directory: Path,  # np. Path("data/parsed")
    ) -> IndexBuildReport:
        """
        Description:
        Indeksuje katalog artefaktów do kolekcji i zwraca, co zrobił. Czyta się jak lista kroków;
        szczegóły siedzą w prywatnych helperach niżej.

        Example args:
            directory=Path("data/parsed")

        Example result:
            IndexBuildReport(read=200, indexed=171, filtered=QualityReport(…), warnings=[])

        Raises:
            NotADirectoryError: ścieżka nie istnieje albo nie jest katalogiem
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        """
        tickets = self._read(directory)
        report  = filter_tickets(tickets)
        kept    = self._kept_tickets(tickets, report)

        await self._qdrant.ensure_collection(vector_size=self._vector_size)
        indexed = await self._upsert(kept)

        # Same liczby: payloady niosą treść zgłoszeń, czyli dane klienta, którym miejsce najwyżej
        # na DEBUG (CLAUDE.md -> „Logi i obserwowalność").
        logger.info(
            "index build collection=%s read=%d indexed=%d dropped=%d",
            self._qdrant.collection,
            len(tickets),
            indexed,
            len(report.dropped),
        )

        warning = drop_rate_warning(report)

        build_report = IndexBuildReport(
            read     = len(tickets),
            indexed  = indexed,
            filtered = report,
            warnings = [warning] if warning else [],
        )

        return build_report

    async def rebuild(
        self,
        directory: Path,  # np. Path("data/parsed")
    ) -> IndexBuildReport:
        """
        Description:
        Kasuje kolekcję i buduje ją od zera. Bezpieczne z konstrukcji, a nie dzięki ostrożności:
        indeks da się odbudować z `data/parsed/` tą samą komendą (zasada 8), więc niszczona jest
        pochodna.

        Osobna metoda zamiast flagi w `build()`, bo obie różnią się tym, czym RYZYKUJĄ, a nie tym,
        jak działają — a CLI jedną z nich musi osłonić potwierdzeniem.

        Example args:
            directory=Path("data/parsed")

        Example result:
            IndexBuildReport(read=200, indexed=171, …)

        Raises:
            NotADirectoryError: ścieżka nie istnieje albo nie jest katalogiem
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
        """
        await self._qdrant.delete_collection()

        return await self.build(directory)

    def _read(
        self,
        directory: Path,  # np. Path("data/parsed")
    ) -> list[ParsedTicket]:
        """
        Description:
        Czyta każdy artefakt z katalogu, w kolejności posortowanej, żeby dwa przebiegi po tym
        samym korpusie dawały porównywalne raporty.

        Wadliwy artefakt przerywa przebieg, zamiast zostać pominięty: `helpdesk tickets validate`
        istnieje po to, żeby takie wyłapać wcześniej, a ciche zaindeksowanie 199 z 200 rekordów
        zostawiłoby lukę, której potem nikt nie zobaczy.

        Example args:
            directory=Path("data/parsed")

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
            EmbeddingError: embedder jest nieosiągalny albo zwrócił inną liczbę wektorów
            DbQdrantError: Qdrant jest nieosiągalny albo odrzucił zapis
        """
        written = 0

        for start in range(0, len(tickets), EMBED_BATCH_SIZE):
            batch = tickets[start : start + EMBED_BATCH_SIZE]
            # Ten sam tekst składa zapytanie w `find_tickets_vector` — obie strony przez
            # `build_embedding_text()`, żeby nie rozjechały się bezgłośnie.
            texts = [ticket.embedding_text() for ticket in batch]

            problem_vectors = await self._embedder.embed_passage(texts)
            sts_vectors     = await self._embedder.embed_sts(texts)

            points = [
                TicketPoint.from_ticket(
                    ticket         = ticket,
                    vector_problem = problem_vector,
                    vector_sts     = sts_vector,
                )
                for ticket, problem_vector, sts_vector in zip(
                    batch, problem_vectors, sts_vectors, strict=True
                )
            ]

            written += await self._qdrant.upsert_points(points)

        return written
