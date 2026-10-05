"""
Description:
Prawdziwe narzędzie `find_docs_vector`: na zapytanie agenta znajduje w Qdrancie sekcje
dokumentacji bliskie znaczeniowo i oddaje ich opisy z podobieństwem. Nie woła LLM-a — tylko
embedder i Qdranta.

    zapytanie agenta → wektor (tryb query) → Qdrant: najbliższy fragment każdej sekcji
                     → próg `RAG_DOCS_SCORE_MIN` → opisy sekcji z podobieństwem

Przed — zapytanie agenta:

    FindDocsVectorQuery(text="kto może opatrzyć dokument pieczęcią elektroniczną urzędu")

Po — wynik `find()` (Qdrant oddał 5 sekcji, próg 0.37 przeszły 2):

    FindDocsVectorResult(
        sections = [
            FoundSection(score=0.472, section=DocSection(section_id="adm-wykaz-uprawnien", …)),
            FoundSection(score=0.414, section=DocSection(section_id="adm-kancelaria-…", …)),
        ],
        dropped_below_threshold = 3,
    )

Co się dzieje po drodze:

1. Embedder liczy wektor zapytania w trybie query.
2. Qdrant oddaje `RAG_TOP_K` najbliższych SEKCJI: w kolekcji leżą fragmenty, ale każda sekcja
   wraca raz, z podobieństwem swojego najbliższego fragmentu.
3. Sekcje poniżej `RAG_DOCS_SCORE_MIN` odpadają, ale są policzone w `dropped_below_threshold`.
4. Z payloadu każdego trafienia wraca opis sekcji z metryczki; treść czyta `read_docs`.

O czym pamiętać przy zmianach:

- Próg jest osobny od progu zgłoszeń (`RAG_SCORE_MIN`): sekcja dokumentacji i karta zgłoszenia
  to inne teksty i ich podobieństwa do zapytania mają inne rozkłady.
- Ile pobrać i gdzie uciąć, ustawia konfiguracja, nie agent — zapytanie niesie tylko to, czego
  szukać.
- Jednostką wyniku jest sekcja, ta sama co w `find_docs_text` i `read_docs`, więc identyfikator
  znaleziony którąkolwiek drogą da się odczytać.
- Payload niezgodny z `DocSection` znaczy, że indeks zbudowano inną wersją kontraktu. Czekanie
  tego nie naprawi, stąd `DbQdrantConfigError`, a nie błąd „spróbuj później".
"""

import logging

from pydantic import ValidationError

from app.agent_tools.docs.find_docs_vector.base import FindDocsVectorToolBase
from app.agent_tools.docs.find_docs_vector.models import (
    FindDocsVectorQuery,
    FindDocsVectorResult,
    FoundSection,
)
from app.core_model.docs.doc_section import DocSection
from app.db_qdrant import DbQdrantConfigError, DocHit, DocsCollection
from app.engine_embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# Do ilu miejsc po przecinku model widzi podobieństwo. Dalsze cyfry to szum, a nie informacja.
SCORE_DIGITS = 3


def found_section_from_hit(
    hit: DocHit,  # np. DocHit(point_id="bc92…", score=0.4721, payload={"section_id": "adm-…", …})
) -> FoundSection:
    """
    Description:
    Zamienia trafienie z Qdranta na element wyniku: opis sekcji z payloadu i zaokrąglone
    podobieństwo.

    Example args:
        hit=DocHit(point_id="bc92…", score=0.4721, payload={"section_id": "adm-wykaz-…", …})

    Example result:
        FoundSection(score=0.472, section=DocSection(section_id="adm-wykaz-uprawnien", …))

    Raises:
        DbQdrantConfigError: payload nie spełnia kontraktu `DocSection`
    """
    try:
        section = DocSection.model_validate(hit.payload)
    except ValidationError as exc:
        fields = sorted({
            ".".join(str(part) for part in error["loc"]) or "rekord"
            for error in exc.errors()
        })

        # `from None`: błąd Pydantica cytuje wartości pól, a w logach mają być same nazwy.
        raise DbQdrantConfigError(
            f"payload punktu {hit.point_id!r} nie spełnia kontraktu DocSection "
            f"(pola: {', '.join(fields)}) — indeks zbudowano inną wersją kontraktu, "
            f"przebuduj go: helpdesk docs index"
        ) from None

    found = FoundSection(
        score   = round(hit.score, SCORE_DIGITS),
        section = section,
    )

    return found


class FindDocsVectorTool(FindDocsVectorToolBase):
    """
    Description:
    `find_docs_vector` na prawdziwym indeksie: embedder liczy wektor zapytania, Qdrant znajduje
    najbliższe sekcje dokumentacji, próg odcina za słabe.

    Do czego:
    Wyszukiwanie w dokumentacji po znaczeniu w grafach `search`, `suggest_questions`
    i `suggest_solution`. Tylko do odczytu: nic tu nie zapisuje do indeksu.

    Flow:
        1. `find()` zamienia tekst zapytania na wektor w trybie query.
        2. Kolekcja dokumentacji oddaje `top_k` najbliższych sekcji.
        3. Próg `score_min` dzieli je na zwrócone i policzone jako odcięte.
        4. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        embedder:  EmbeddingClient,  # np. EmbeddingClient(base_url="http://embedder:8000")
        docs:      DocsCollection,   # np. DocsCollection(QdrantClient(…), "docs", 768)
        top_k:     int,              # np. 5 — RAG_TOP_K, liczba sekcji
        score_min: float,            # np. 0.37 — RAG_DOCS_SCORE_MIN, podobieństwo cosinusowe
    ):
        """
        Description:
        Spina narzędzie z embedderem i kolekcją dokumentacji oraz z dwoma parametrami strojenia.
        Oba są wstrzykiwane, nie budowane tutaj (zasada 4).

        Example args:
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            docs=DocsCollection(QdrantClient(base_url="http://qdrant:6333"), "docs", 768)
            top_k=5
            score_min=0.37

        Example result:
            FindDocsVectorTool gotowe do wyszukiwania w kolekcji `docs`
        """
        self._embedder  = embedder
        self._docs      = docs
        self._top_k     = top_k
        self._score_min = score_min

    async def find(
        self,
        query: FindDocsVectorQuery,  # np. FindDocsVectorQuery(text="uprawnienia kancelaria")
    ) -> FindDocsVectorResult:
        """
        Description:
        Znajduje sekcje dokumentacji podobne znaczeniowo do zapytania, od najbardziej podobnej,
        już przycięte progiem.

        Example args:
            query=FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            FindDocsVectorResult(sections=[FoundSection(score=0.581, section=DocSection(…))],
                                 dropped_below_threshold=2)

        Raises:
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
            DbQdrantError: Qdrant jest nieosiągalny albo odpowiedział błędem
            DbQdrantConfigError: payload trafienia nie spełnia kontraktu `DocSection`
        """
        # --- wektor zapytania: tryb query, bo w kolekcji leżą wektory passage ---
        vectors = await self._embedder.embed_query([query.text])

        # --- wyszukanie: każda sekcja raz, z najbliższym fragmentem ---
        hits = await self._docs.search(vector=vectors[0], limit=self._top_k)

        # --- próg: odcięte liczymy, zamiast gubić ---
        kept    = [hit for hit in hits if hit.score >= self._score_min]
        dropped = len(hits) - len(kept)

        # Same liczby: zapytanie agenta niesie treść zgłoszenia.
        logger.info(
            "find_docs_vector sections=%d dropped=%d score_min=%.3f",
            len(kept),
            dropped,
            self._score_min,
        )

        result = FindDocsVectorResult(
            sections                = [found_section_from_hit(hit) for hit in kept],
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
        await self._docs.aclose()
