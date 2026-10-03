"""
Description:
Prawdziwe narzędzie `find_tickets_vector`: na zapytanie agenta znajduje w Qdrancie historyczne
zgłoszenia o podobnym problemie. Nie woła LLM-a ani parsera — tylko embedder i Qdranta.

    zapytanie agenta → tekst do embeddingu → wektor (tryb query) → Qdrant (wektory `problem`)
                     → próg `RAG_SCORE_MIN` → zgłoszenia z payloadu

Przed — zapytanie agenta:

    FindTicketsVectorQuery(
        problem  = "Nie przychodzą przesyłki z e-Doręczeń",
        symptoms = "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
    )

Po — wynik `search()` (Qdrant oddał 5 trafień, próg 0.48 przeszły 2):

    FindTicketsVectorResult(
        items = [
            FoundTicket(score=0.71, ticket=ParsedTicket(ticket_id="90001", …)),
            FoundTicket(score=0.52, ticket=ParsedTicket(ticket_id="90003", …)),
        ],
        dropped_below_threshold = 3,
    )

Co się dzieje po drodze:

1. Z `problem` i `symptoms` powstaje tekst do embeddingu — tą samą funkcją, którą indeksacja
   składa tekst rekordu (`build_embedding_text()`).
2. Embedder liczy z niego wektor w trybie query.
3. Qdrant oddaje `RAG_TOP_K` najbliższych punktów, zawsze po wektorach `problem`.
4. Trafienia poniżej `RAG_SCORE_MIN` odpadają, ale są policzone w `dropped_below_threshold`.
5. Payload każdego trafienia staje się z powrotem `ParsedTicket`.

Tekst dla modelu i listę źródeł robi z wyniku klasa wspólna z atrapą (`base.py`).

O czym pamiętać przy zmianach:

- Wektor query wolno porównywać wyłącznie z wektorami `problem`. Szukanie po `sts` nie jest
  błędem, tylko daje trochę gorsze wyniki, więc nikt tego nie zauważy.
- Ile pobrać i gdzie uciąć, ustawia konfiguracja, nie agent — zapytanie niesie tylko to, czego
  szukać.
- Payload niezgodny z `ParsedTicket` znaczy, że indeks zbudowano inną wersją kontraktu. Czekanie
  tego nie naprawi, stąd `RetrievalConfigError`, a nie błąd „spróbuj później".
"""

import logging

from pydantic import ValidationError

from app.embedding import EmbeddingClient
from app.model.ticket_parsed import ParsedTicket
from app.retrieval import VECTOR_PROBLEM, QdrantClient, RetrievalConfigError, TicketHit
from app.service.builder_embedding_text import build_embedding_text
from app.tools.find_tickets_vector.base import FindTicketsVectorToolBase
from app.tools.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)

logger = logging.getLogger(__name__)


def found_ticket_from_hit(
    hit: TicketHit,  # np. TicketHit(point_id="df3b…", score=0.71, payload={…})
) -> FoundTicket:
    """
    Description:
    Zamienia trafienie z Qdranta na element wyniku: payload wraca do `ParsedTicket`, z którego
    został zapisany przy indeksacji.

    Example args:
        hit=TicketHit(point_id="df3b…", score=0.71, payload={"ticket_id": "90001", …})

    Example result:
        FoundTicket(score=0.71, ticket=ParsedTicket(ticket_id="90001", …))

    Raises:
        RetrievalConfigError: payload nie spełnia kontraktu `ParsedTicket`
    """
    try:
        ticket = ParsedTicket.model_validate(hit.payload)
    except ValidationError as exc:
        fields = sorted({
            ".".join(str(part) for part in error["loc"]) or "rekord"
            for error in exc.errors()
        })

        # `from None`: błąd Pydantica cytuje wartości pól, czyli treść zgłoszenia — nie do logów.
        raise RetrievalConfigError(
            f"payload zgłoszenia {hit.ticket_id!r} nie spełnia kontraktu ParsedTicket "
            f"(pola: {', '.join(fields)}) — indeks zbudowano inną wersją kontraktu, "
            f"przebuduj go: helpdesk rag reindex"
        ) from None

    found = FoundTicket(
        score  = hit.score,
        ticket = ticket,
    )

    return found


class FindTicketsVectorTool(FindTicketsVectorToolBase):
    """
    Description:
    `find_tickets_vector` na prawdziwym indeksie: embedder liczy wektor zapytania, Qdrant znajduje
    najbliższe zgłoszenia, próg odcina za słabe.

    Do czego:
    Źródło wiedzy agenta w grafach `search`, `suggest_questions` i `suggest_solution`. Tylko do
    odczytu: nic tu nie zapisuje do indeksu.

    Flow:
        1. `search()` składa tekst zapytania i zamienia go na wektor w trybie query.
        2. Qdrant oddaje `top_k` najbliższych punktów po wektorach `problem`.
        3. Próg `score_min` dzieli je na zwrócone i policzone jako odcięte.
        4. `render_for_model()` i `cite()` z klasy bazowej robią z wyniku tekst i źródła.
    """

    def __init__(
        self,
        embedder:  EmbeddingClient,  # np. EmbeddingClient(base_url="http://embedder:8000")
        qdrant:    QdrantClient,     # np. QdrantClient(base_url="http://qdrant:6333", …)
        top_k:     int,              # np. 5 — RAG_TOP_K
        score_min: float,            # np. 0.48 — RAG_SCORE_MIN, podobieństwo cosinusowe
    ):
        """
        Description:
        Spina narzędzie z embedderem i Qdrantem oraz z dwoma parametrami strojenia. Klienty są
        wstrzykiwane, nie budowane tutaj (zasada 4).

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            qdrant=QdrantClient(base_url="http://qdrant:6333", collection="tickets")
            top_k=5
            score_min=0.48

        Example result:
            FindTicketsVectorTool gotowe do wyszukiwania w kolekcji `tickets`
        """
        self._embedder  = embedder
        self._qdrant    = qdrant
        self._top_k     = top_k
        self._score_min = score_min

    async def search(
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
            FindTicketsVectorResult(items=[FoundTicket(score=0.71, …)], dropped_below_threshold=3)

        Raises:
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
            RetrievalError: Qdrant jest nieosiągalny albo odpowiedział błędem
            RetrievalConfigError: payload trafienia nie spełnia kontraktu `ParsedTicket`
        """
        # --- tekst i wektor zapytania ---
        text = build_embedding_text(
            problem  = query.problem,
            symptoms = query.symptoms,
        )
        vectors = await self._embedder.embed_query([text])

        # --- wyszukanie: zawsze po wektorach `problem`, nigdy `sts` ---
        hits = await self._qdrant.search(
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
            items                   = [found_ticket_from_hit(hit) for hit in kept],
            dropped_below_threshold = dropped,
        )

        return result

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia obu klientów. Sprzątający woła tylko to i nie musi wiedzieć, z czego
        narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._embedder.aclose()
        await self._qdrant.aclose()
