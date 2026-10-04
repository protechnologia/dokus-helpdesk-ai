"""
Description:
Kolekcja dokumentacji w Qdrancie. Punkt to jedna sekcja z metryczki (`DocSection`) z jednym
nazwanym wektorem; treści sekcji tu nie ma — leży w Postgresie i daje ją `read_docs`.

Wyszukiwanie wektorowe, tekstowe i odczyt wskazują ten sam identyfikator sekcji.

O czym pamiętać przy zmianach:

- Schemat kolekcji to `VECTORS` w klasie niżej i wymiar z konfiguracji. Zmiana nie dociera do
  istniejącej kolekcji: `ensure()` jej nie naprawia, tylko odmawia, a kolekcję kasuje się
  i odbudowuje z plików dokumentacji.
- Wektor jest jeden, więc `search()` nie bierze jego nazwy. Gdy dojdzie drugi, nazwa staje się
  argumentem wymaganym, jak w kolekcji zgłoszeń.
- Co się embeduje i czy sekcja dzieli się na fragmenty, rozstrzyga pomiar (CLAUDE.md -> p. 8).
  Przy fragmentach zmieni się liczenie identyfikatora punktu; `section_id` zostaje w payloadzie.
- Wołający podaje identyfikatory sekcji; identyfikatory punktów liczy kolekcja.
"""

from collections.abc import Sequence

from app.db_qdrant.collection.base import VectorCollection
from app.db_qdrant.hit.docs import DocHit
from app.db_qdrant.point.base import point_id_for
from app.db_qdrant.point.docs import VECTOR_SECTION, DocPoint


class DocsCollection(VectorCollection):
    """
    Description:
    Kolekcja dokumentacji: zakładanie, zapis sekcji, szukanie po wektorze i odczyt po
    identyfikatorze sekcji.

    Do czego:
    Stąd `find_docs_vector` weźmie sekcje pasujące znaczeniowo do zagadnienia, a import
    dokumentacji tu je zapisze (CLAUDE.md -> p. 8, p. 49). Mechanika żądań stoi w klasie bazowej.

    Flow:
        1. Import: `ensure()` z klasy bazowej, potem `upsert()`; przebudowa zaczyna od `drop()`.
        2. Narzędzie: `search()` → trafienia `DocHit`, od najbardziej podobnego.
        3. Odczyt: `read_by_id()` → punkty `DocPoint` o podanych identyfikatorach sekcji.
    """

    # Nazwane wektory kolekcji dokumentacji — jej cały schemat poza wymiarem z konfiguracji.
    VECTORS = (VECTOR_SECTION,)

    async def upsert(
        self,
        points: Sequence[DocPoint],  # np. [DocPoint.from_section(section, [0.0123, -0.0456])]
    ) -> int:
        """
        Description:
        Zapisuje sekcje i oddaje, ile zapisano. Punkt tej samej sekcji jest nadpisywany.

        Example args:
            points=[DocPoint(point_id="c8810a95-…", payload={"section_id": "adm-…", …}, …)]

        Example result:
            1

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odrzucił zapis
        """
        written = await self._upsert([point.to_qdrant() for point in points])

        return written

    async def search(
        self,
        vector: list[float],  # np. [0.0123, -0.0456] — z embed_query()
        limit:  int,          # np. 5 — RAG_TOP_K
    ) -> list[DocHit]:
        """
        Description:
        Znajduje `limit` sekcji najbliższych wektorowi, od najbardziej podobnej.

        Example args:
            vector=[0.0123, -0.0456]
            limit=5

        Example result:
            [DocHit(point_id="c8810a95-…", score=0.74, payload={"section_id": "adm-…", …})]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo odpowiedź ma
                nierozpoznany kształt
        """
        entries = await self._search(vector=vector, vector_name=VECTOR_SECTION, limit=limit)
        hits    = [DocHit.from_qdrant(entry) for entry in entries]

        return hits

    async def read_by_id(
        self,
        section_ids: Sequence[str],  # np. ["adm-kancelaria-edoreczenia"]
    ) -> list[DocPoint]:
        """
        Description:
        Oddaje sekcje o podanych identyfikatorach, w kolejności identyfikatorów — całe punkty,
        z opisem sekcji i wektorem. Identyfikatora, którego w kolekcji nie ma, po prostu nie ma
        w wyniku.

        Example args:
            section_ids=["adm-kancelaria-edoreczenia"]

        Example result:
            [DocPoint(point_id="c8810a95-…", payload={"section_id": "adm-…", …}, …)]

        Raises:
            DbQdrantConfigError: punkt nie ma nazwanego wektora sekcji
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo odpowiedź ma
                nierozpoznany kształt
        """
        point_ids = [point_id_for(section_id) for section_id in section_ids]
        entries   = await self._read_by_id(point_ids)
        points    = [DocPoint.from_qdrant(entry) for entry in entries]

        return points
