"""
Description:
Prawdziwe narzędzie `find_tickets_vector`: na zapytanie agenta znajduje w Qdrancie historyczne
zgłoszenia o podobnym problemie i oddaje ich numery. Nie woła LLM-a ani parsera — tylko embedder
i Qdranta.

    zapytanie agenta → tekst do embeddingu → wektor (tryb query) → Qdrant (wektory `problem`)
                     → próg `RAG_SCORE_MIN` → numery zgłoszeń z podobieństwem

Przed — zapytanie agenta:

    FindTicketsVectorQuery(
        problem  = "Nie przychodzą przesyłki z e-Doręczeń",
        symptoms = "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
    )

Po — wynik `find()` (Qdrant oddał 5 trafień, próg 0.48 przeszły 2):

    FindTicketsVectorResult(
        tickets = [
            FoundTicket(ticket_id="90001", score=0.71),
            FoundTicket(ticket_id="90003", score=0.52),
        ],
        dropped_below_threshold = 3,
    )

Co się dzieje po drodze:

1. Z `problem` i `symptoms` powstaje tekst do embeddingu — tą samą funkcją, którą indeksacja
   składa tekst rekordu (`build_embedding_text()`).
2. Embedder liczy z niego wektor w trybie query.
3. Qdrant oddaje `RAG_TOP_K` najbliższych punktów, zawsze po wektorach `problem`.
4. Trafienia poniżej `RAG_SCORE_MIN` odpadają, ale są policzone w `dropped_below_threshold`.
5. Z każdego trafienia zostaje numer zgłoszenia i podobieństwo; kartę czyta `read_tickets_card`.

O czym pamiętać przy zmianach:

- Wektor query wolno porównywać wyłącznie z wektorami `problem`. Szukanie po `sts` nie jest
  błędem, tylko daje trochę gorsze wyniki, więc nikt tego nie zauważy.
- Ile pobrać i gdzie uciąć, ustawia konfiguracja, nie agent — zapytanie niesie tylko to, czego
  szukać.
- Próg jest jedynym miejscem, w którym KOD mówi „nic nie znaleziono": bez niego wyszukiwanie
  zawsze oddawałoby komplet numerów, także dla zgłoszenia bez odpowiednika w bazie.
- Trafienie bez numeru zgłoszenia w payloadzie znaczy, że indeks zbudowano inaczej. Czekanie
  tego nie naprawi, stąd `DbQdrantConfigError`, a nie błąd „spróbuj później".
"""

import logging

from app.agent_tools.tickets.find_tickets_vector.base import FindTicketsVectorToolBase
from app.agent_tools.tickets.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)
from app.core_service.builder_embedding_text import build_embedding_text
from app.db_qdrant import VECTOR_PROBLEM, DbQdrantConfigError, TicketHit, TicketsCollection
from app.engine_embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# Do ilu miejsc po przecinku model widzi podobieństwo. Dalsze cyfry to szum, a nie informacja.
SCORE_DIGITS = 3


def found_ticket_from_hit(
    hit: TicketHit,  # np. TicketHit(point_id="df3b…", score=0.7134, payload={…})
) -> FoundTicket:
    """
    Description:
    Zamienia trafienie z Qdranta na element wyniku: numer zgłoszenia z payloadu i zaokrąglone
    podobieństwo.

    Example args:
        hit=TicketHit(point_id="df3b…", score=0.7134, payload={"ticket_id": "90001", …})

    Example result:
        FoundTicket(ticket_id="90001", score=0.713)

    Raises:
        DbQdrantConfigError: payload trafienia nie ma numeru zgłoszenia
    """
    if not hit.ticket_id:
        raise DbQdrantConfigError(
            f"punkt {hit.point_id!r} nie ma `ticket_id` w payloadzie — indeks zbudowano inną "
            f"wersją kontraktu, przebuduj go: helpdesk rag reindex"
        )

    found = FoundTicket(
        ticket_id = hit.ticket_id,
        score     = round(hit.score, SCORE_DIGITS),
    )

    return found


class FindTicketsVectorTool(FindTicketsVectorToolBase):
    """
    Description:
    `find_tickets_vector` na prawdziwym indeksie: embedder liczy wektor zapytania, Qdrant znajduje
    najbliższe zgłoszenia, próg odcina za słabe.

    Do czego:
    Wyszukiwanie zgłoszeń po znaczeniu w grafach `search`, `suggest_questions`
    i `suggest_solution`. Tylko do odczytu: nic tu nie zapisuje do indeksu.

    Flow:
        1. `find()` składa tekst zapytania i zamienia go na wektor w trybie query.
        2. Qdrant oddaje `top_k` najbliższych punktów po wektorach `problem`.
        3. Próg `score_min` dzieli je na zwrócone i policzone jako odcięte.
        4. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        embedder:  EmbeddingClient,    # np. EmbeddingClient(base_url="http://embedder:8000")
        tickets:   TicketsCollection,  # np. TicketsCollection(QdrantClient(…), "tickets", 768)
        top_k:     int,                # np. 5 — RAG_TOP_K
        score_min: float,              # np. 0.48 — RAG_SCORE_MIN, podobieństwo cosinusowe
    ):
        """
        Description:
        Spina narzędzie z embedderem i kolekcją zgłoszeń oraz z dwoma parametrami strojenia.
        Oba są wstrzykiwane, nie budowane tutaj (zasada 4).

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            tickets=TicketsCollection(QdrantClient(base_url="http://qdrant:6333"), "tickets", 768)
            top_k=5
            score_min=0.48

        Example result:
            FindTicketsVectorTool gotowe do wyszukiwania w kolekcji `tickets`
        """
        self._embedder  = embedder
        self._tickets   = tickets
        self._top_k     = top_k
        self._score_min = score_min

    async def find(
        self,
        query: FindTicketsVectorQuery,  # np. FindTicketsVectorQuery(problem="Brak przesyłek", …)
    ) -> FindTicketsVectorResult:
        """
        Description:
        Znajduje zgłoszenia o problemie podobnym do zapytania, od najbardziej podobnego, już
        przycięte progiem.

        Example args:
            query=FindTicketsVectorQuery(problem="Nie przychodzą przesyłki z e-Doręczeń",
                                         symptoms="Brak nowych przesyłek w skrzynce")

        Example result:
            FindTicketsVectorResult(tickets=[FoundTicket(ticket_id="90001", score=0.71)],
                                    dropped_below_threshold=3)

        Raises:
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
            DbQdrantError: Qdrant jest nieosiągalny albo odpowiedział błędem
            DbQdrantConfigError: payload trafienia nie ma numeru zgłoszenia
        """
        # --- tekst i wektor zapytania ---
        text = build_embedding_text(
            problem  = query.problem,
            symptoms = query.symptoms,
        )
        vectors = await self._embedder.embed_query([text])

        # --- wyszukanie: zawsze po wektorach `problem`, nigdy `sts` ---
        hits = await self._tickets.search(
            vector      = vectors[0],
            vector_name = VECTOR_PROBLEM,
            limit       = self._top_k,
        )

        # --- próg: odcięte liczymy, zamiast gubić ---
        kept    = [hit for hit in hits if hit.score >= self._score_min]
        dropped = len(hits) - len(kept)

        # Same liczby: treść zapytania i trafień to dane klienta.
        logger.info(
            "find_tickets_vector hits=%d dropped=%d score_min=%.3f",
            len(kept),
            dropped,
            self._score_min,
        )

        result = FindTicketsVectorResult(
            tickets                 = [found_ticket_from_hit(hit) for hit in kept],
            dropped_below_threshold = dropped,
        )

        return result

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia embeddera i Qdranta. Sprzątający woła tylko to i nie musi wiedzieć,
        z czego narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._embedder.aclose()
        await self._tickets.aclose()
