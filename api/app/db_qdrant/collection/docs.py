"""
Description:
Kolekcja dokumentacji w Qdrancie. Punkt to jeden fragment sekcji z jednym nazwanym wektorem
i opisem sekcji z metryczki (`DocSection`) w payloadzie; sekcja ma tyle punktów, na ile
fragmentów pocięto jej treść. Samej treści tu nie ma — leży w Postgresie i daje ją `read_docs`.

Wyszukiwanie wektorowe, tekstowe i odczyt wskazują ten sam identyfikator sekcji.

O czym pamiętać przy zmianach:

- Schemat kolekcji to `VECTORS` w klasie niżej i wymiar z konfiguracji. Zmiana nie dociera do
  istniejącej kolekcji: `ensure()` jej nie naprawia, tylko odmawia, a kolekcję kasuje się
  i odbudowuje z plików dokumentacji.
- Wektor jest jeden, więc `search()` nie bierze jego nazwy. Gdy dojdzie drugi, nazwa staje się
  argumentem wymaganym, jak w kolekcji zgłoszeń.
- `search()` oddaje SEKCJE, nie fragmenty: Qdrant grupuje punkty po `section_id` i z każdej
  sekcji zwraca najbliższy fragment. Zwijanie po naszej stronie wymagałoby pobierania z zapasem,
  a zapas zależy od najdłuższej sekcji — na paczce syntetycznej pięć sekcji wymagało do 25
  fragmentów.
- Odczytu po identyfikatorze tu nie ma, inaczej niż w kolekcji zgłoszeń: z `section_id` nie da
  się policzyć, ile sekcja ma punktów, a treść sekcji i tak czyta się z Postgresa.
"""

from collections.abc import Sequence

from app.db_qdrant.collection.base import VectorCollection
from app.db_qdrant.hit.docs import DocHit
from app.db_qdrant.point.docs import VECTOR_SECTION, DocPoint

# Pole payloadu wspólne dla fragmentów jednej sekcji — po nim Qdrant zwija trafienia do sekcji.
GROUP_BY_SECTION = "section_id"


class DocsCollection(VectorCollection):
    """
    Description:
    Kolekcja dokumentacji: zakładanie, zapis fragmentów sekcji i szukanie sekcji po wektorze.

    Do czego:
    Tu indekser dokumentacji zapisuje fragmenty, a `find_docs_vector` bierze stąd sekcje pasujące
    znaczeniowo do zagadnienia. Mechanika żądań stoi w klasie bazowej.

    Flow:
        1. Indeksacja: `drop()` i `ensure()` z klasy bazowej, potem `upsert()`.
        2. Narzędzie: `search()` → trafienia `DocHit`, po jednym na sekcję, od najbardziej
           podobnej.
    """

    # Nazwane wektory kolekcji dokumentacji — jej cały schemat poza wymiarem z konfiguracji.
    VECTORS = (VECTOR_SECTION,)

    async def upsert(
        self,
        points: Sequence[DocPoint],  # np. [DocPoint.from_fragment(section, 0, [0.0123, -0.0456])]
    ) -> int:
        """
        Description:
        Zapisuje fragmenty sekcji i oddaje, ile zapisano. Punkt tego samego fragmentu jest
        nadpisywany.

        Example args:
            points=[DocPoint(point_id="bc925b88-…", payload={"section_id": "adm-…", …}, …)]

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
        limit:  int,          # np. 5 — RAG_TOP_K; liczba sekcji, nie fragmentów
    ) -> list[DocHit]:
        """
        Description:
        Znajduje `limit` sekcji najbliższych wektorowi, od najbardziej podobnej. Każda sekcja
        wraca raz, z podobieństwem swojego najbliższego fragmentu.

        Example args:
            vector=[0.0123, -0.0456]
            limit=5

        Example result:
            [DocHit(point_id="bc925b88-…", score=0.74, payload={"section_id": "adm-…", …})]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo odpowiedź ma
                nierozpoznany kształt
        """
        entries = await self._search_groups(
            vector      = vector,
            vector_name = VECTOR_SECTION,
            group_by    = GROUP_BY_SECTION,
            limit       = limit,
        )
        hits = [DocHit.from_qdrant(entry) for entry in entries]

        return hits
