"""
Description:
Wspólna mechanika kolekcji Qdranta: zakładanie ze sprawdzeniem schematu, kasowanie, licznik, zapis
partiami, szukanie po wektorze i odczyt po identyfikatorach. Po tej klasie dziedziczą kolekcje
materiałów (`TicketsCollection`, `DocsCollection`); każda mówi u siebie, jakie ma wektory
(`VECTORS`) i jakie punkty przyjmuje.

Schemat kolekcji to trzy rzeczy: nazwy wektorów (z podklasy), ich wymiar (z konfiguracji, podany
przy budowie obiektu) i metryka (wspólna, niżej).

Żądania do Qdranta, wszystkie pod `/collections/<nazwa>`:

| metoda             | żądanie                     | co robi                                      |
|--------------------|-----------------------------|----------------------------------------------|
| `ensure()`         | `GET`, potem `PUT`          | sprawdza schemat albo zakłada kolekcję       |
| `drop()`           | `GET`, potem `DELETE`       | kasuje kolekcję                              |
| `count()`          | `POST /points/count`        | dokładna liczba punktów                      |
| `_upsert()`        | `PUT /points`               | zapis punktów partiami                       |
| `_search()`        | `POST /points/query`        | najbliższe punkty w jednej przestrzeni       |
| `_search_groups()` | `POST /points/query/groups` | najbliższy punkt każdej z najbliższych grup  |
| `_read_by_id()`    | `POST /points`              | punkty o podanych identyfikatorach i wektory |

O czym pamiętać przy zmianach:

- Kolekcja przy rozjeździe NIE jest naprawiana. Inny wymiar albo brak nazwanego wektora znaczy,
  że zbudowano ją pod inny model; komunikat podaje obie liczby, bo samo „768 ≠ 1024" nie mówi,
  którą stronę poprawić.
- Metryka `Cosine` jest wspólna: embedder oddaje wektory jednostkowe i na takich mierzono próg
  `RAG_SCORE_MIN`. Qdrant normalizuje wektor przy zapisie, więc odczytany ma ten sam kierunek,
  ale nie musi mieć tych samych liczb.
- Szukanie zawsze w jednej, nazwanej przestrzeni. Szukanie po niewłaściwym wektorze nie jest
  błędem — oddaje wiarygodnie wyglądające, trochę gorsze wyniki.
- Nazwa kolekcji trafia do ścieżki żądania, więc jest sprawdzana wzorcem przy budowie obiektu.
- W logach na INFO same liczby i nazwy: payloady niosą treść zgłoszeń, czyli dane klienta.
"""

import logging
import re
from collections.abc import Sequence

from app.db_qdrant.client import QdrantClient
from app.db_qdrant.errors import DbQdrantConfigError, DbQdrantError

logger = logging.getLogger(__name__)

# Metryka każdego nazwanego wektora. Jej zmiana zmieniłaby znaczenie `RAG_SCORE_MIN`.
DISTANCE = "Cosine"

# Ile punktów idzie w jednym żądaniu zapisu: korpus 1500 rekordów to kilkadziesiąt żądań, a jedna
# porażka nie gubi pracy długiego przebiegu.
UPSERT_BATCH_SIZE = 64

# Dozwolona nazwa kolekcji: litery, cyfry, podkreślenia i łączniki, od litery, do 255 znaków
# (limit Qdranta). Wszystko inne to błąd — także nazwa pusta.
COLLECTION_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,254}")


class VectorCollection:
    """
    Description:
    Mechanika wspólna kolekcji Qdranta: zakładanie, kasowanie, licznik, zapis, szukanie i odczyt.

    Do czego:
    Baza kolekcji materiałów. Nazwy wektorów bierze z `VECTORS` podklasy, wymiar z konstruktora,
    a kształtu punktów nie zna — pracuje na słownikach w kształcie Qdranta. Kod spoza
    `app/db_qdrant/` używa podklas (`TicketsCollection`, `DocsCollection`) i niczego poza nimi.

    Flow:
        1. Budowana z klienta, nazwy i wymiaru wektora; zła nazwa albo wymiar to błąd od razu.
        2. `ensure()` zakłada kolekcję albo sprawdza schemat istniejącej.
        3. `_upsert()` zapisuje punkty, `_search()` i `_search_groups()` szukają,
           `_read_by_id()` czyta — wszystkie na słownikach, a na swoje modele zamienia je
           podklasa.
        4. `count()` liczy punkty, `drop()` kasuje kolekcję.
    """

    # Nazwane wektory kolekcji. Podklasa podaje swoje — to jej schemat.
    VECTORS: tuple[str, ...] = ()

    def __init__(
        self,
        client:      QdrantClient,  # np. QdrantClient(base_url="http://qdrant:6333")
        name:        str,           # np. "tickets"
        vector_size: int,           # np. 768 — EMBEDDING_VECTOR_SIZE
    ):
        """
        Description:
        Zapamiętuje klienta, nazwę kolekcji i wymiar jej wektorów; z Qdrantem się nie łączy.
        Wymiar przychodzi z konfiguracji, bo jest cechą modelu embeddingowego, a nie kolekcji.

        Example args:
            client=QdrantClient(base_url="http://qdrant:6333")
            name="tickets"
            vector_size=768

        Example result:
            VectorCollection „tickets" o wektorach wymiaru 768

        Raises:
            DbQdrantConfigError: nazwa spoza wzorca (pusta, ze spacją, z ukośnikiem…) albo
                wymiar mniejszy niż 1
        """
        if not COLLECTION_NAME.fullmatch(name):
            raise DbQdrantConfigError(
                f"niedozwolona nazwa kolekcji: {name!r} — litery, cyfry, podkreślenia "
                f"i łączniki, od litery"
            )

        if vector_size < 1:
            raise DbQdrantConfigError(
                f"EMBEDDING_VECTOR_SIZE={vector_size} — wymiar wektora musi być dodatni"
            )

        self._client      = client
        self._name        = name
        self._vector_size = vector_size
        self._path        = f"/collections/{name}"

    @property
    def name(self) -> str:
        """
        Description:
        Nazwa kolekcji, tak jak ją podano — do raportów i logów wołającego.

        Example args:
            (brak)

        Example result:
            "tickets"
        """
        return self._name

    async def ensure(self) -> bool:
        """
        Description:
        Upewnia się, że kolekcja istnieje z nazwanymi wektorami podklasy w wymiarze podanym przy
        budowie. Oddaje True, gdy trzeba ją było założyć, i False, gdy zgodna już była. Rozjazdu
        nie naprawia.

        Example args:
            (brak)

        Example result:
            True — kolekcji nie było i została założona

        Raises:
            DbQdrantConfigError: istniejąca kolekcja ma inny wymiar albo nie ma któregoś wektora
            DbQdrantError: Qdrant nie odpowiedział albo odpowiedział błędem
        """
        existing = await self._client.get_or_none(self._path)

        # --- już jest: sprawdź, nigdy nie dopasowuj ---
        if existing is not None:
            self._verify_schema(existing)

            return False

        # --- załóż ---
        logger.info(
            "creating collection=%s vector_size=%d vectors=%s",
            self._name,
            self._vector_size,
            self.VECTORS,
        )
        vectors = {
            name: {"size": self._vector_size, "distance": DISTANCE} for name in self.VECTORS
        }

        await self._client.request("PUT", self._path, json={"vectors": vectors})

        return True

    async def drop(self) -> bool:
        """
        Description:
        Kasuje kolekcję. Oddaje True, gdy coś skasowano, i False, gdy kolekcji nie było — jej
        brak to zwykły stan początkowy. Bezpieczne z konstrukcji: kolekcja odbudowuje się
        z plików jedną komendą (zasada 8).

        Example args:
            (brak)

        Example result:
            True — kolekcja istniała i już jej nie ma

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odpowiedział błędem
        """
        if await self._client.get_or_none(self._path) is None:
            return False

        logger.info("deleting collection=%s", self._name)
        await self._client.request("DELETE", self._path)

        return True

    async def count(self) -> int:
        """
        Description:
        Liczy punkty w kolekcji, dokładnie — liczba przybliżona rozchwiałaby test „dwie
        przebudowy dają ten sam stan".

        Example args:
            (brak)

        Example result:
            171

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, kolekcji nie ma albo odpowiedź ma
                nierozpoznany kształt
        """
        body   = await self._client.request(
            "POST",
            f"{self._path}/points/count",
            json={"exact": True},
        )
        result = body.get("result")
        count  = result.get("count") if isinstance(result, dict) else None

        if not isinstance(count, int):
            raise DbQdrantError(f"Qdrant oddał nierozpoznany licznik kolekcji '{self._name}'")

        return count

    async def aclose(self) -> None:
        """
        Description:
        Zamyka klienta, na którym stoi kolekcja — żeby ten, kto dostał samą kolekcję, mógł po
        sobie posprzątać. Klient bywa wspólny dla kilku kolekcji; zamknięcie przez jedną zamyka
        go wszystkim, a powtórne zamknięcie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    async def _upsert(
        self,
        points: Sequence[dict],  # np. [{"id": "df3b…", "vector": {…}, "payload": {…}}]
    ) -> int:
        """
        Description:
        Zapisuje punkty partiami i oddaje, ile zapisano. Punkt o istniejącym identyfikatorze
        jest nadpisywany. Każda partia czeka na zastosowanie (`wait=true`): przebieg raportuje,
        co zapisał, a kolejny krok to czyta.

        Example args:
            points=[{"id": "df3b51f3-…", "vector": {"problem": […], "sts": […]}, "payload": {…}}]

        Example result:
            1

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odrzucił partię (np. zły wymiar wektora)
        """
        # --- nic do zapisania: powiedz to, bo „0 zapisanych" to poprawny wynik filtru ---
        if not points:
            logger.info("upsert collection=%s points=0 — nothing to write", self._name)

            return 0

        written = 0

        for start in range(0, len(points), UPSERT_BATCH_SIZE):
            batch = points[start : start + UPSERT_BATCH_SIZE]

            await self._client.request(
                "PUT",
                f"{self._path}/points",
                params = {"wait": "true"},
                json   = {"points": list(batch)},
            )

            written += len(batch)

        logger.info("upsert collection=%s points=%d", self._name, written)

        return written

    async def _search(
        self,
        vector:      list[float],  # np. [0.0123, -0.0456] — z embed_query()
        vector_name: str,          # np. "problem" — w której przestrzeni szukać
        limit:       int,          # np. 5 — RAG_TOP_K
    ) -> list[dict]:
        """
        Description:
        Znajduje `limit` najbliższych punktów w JEDNEJ nazwanej przestrzeni, od najbardziej
        podobnego, z payloadem.

        Example args:
            vector=[0.0123, -0.0456]
            vector_name="problem"
            limit=5

        Example result:
            [{"id": "df3b51f3-…", "score": 0.87, "payload": {"ticket_id": "33644", …}}]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo takiego wektora, albo
                odpowiedź ma nierozpoznany kształt
        """
        body = await self._client.request(
            "POST",
            f"{self._path}/points/query",
            json={
                "query": vector,
                "using": vector_name,
                "limit": limit,
                # Bez tego Qdrant oddaje same identyfikatory i podobieństwa.
                "with_payload": True,
            },
        )

        # Wynik zapytania jest o poziom głębiej niż w starszej końcówce wyszukiwania.
        result  = body.get("result")
        entries = result.get("points") if isinstance(result, dict) else None

        if not isinstance(entries, list):
            raise DbQdrantError(
                f"Qdrant oddał nierozpoznany wynik wyszukiwania w kolekcji '{self._name}'"
            )

        logger.info(
            "search collection=%s using=%s limit=%d hits=%d",
            self._name,
            vector_name,
            limit,
            len(entries),
        )

        return entries

    async def _search_groups(
        self,
        vector:      list[float],  # np. [0.0123, -0.0456] — z embed_query()
        vector_name: str,          # np. "section" — w której przestrzeni szukać
        group_by:    str,          # np. "section_id" — pole payloadu wspólne dla grupy
        limit:       int,          # np. 5 — ile GRUP, nie punktów
    ) -> list[dict]:
        """
        Description:
        Znajduje `limit` najbliższych grup punktów w JEDNEJ nazwanej przestrzeni i oddaje
        najbliższy punkt każdej z nich, od najbardziej podobnego, z payloadem. Grupą są punkty
        o tej samej wartości pola payloadu, np. fragmenty jednej sekcji dokumentacji.

        Grupuje Qdrant, nie wołający: pobranie punktów z zapasem i zwinięcie ich u siebie gubi
        grupy, gdy jedna długa sekcja zajmuje cały zapas.

        Example args:
            vector=[0.0123, -0.0456]
            vector_name="section"
            group_by="section_id"
            limit=5

        Example result:
            [{"id": "bc925b88-…", "score": 0.74, "payload": {"section_id": "adm-…", …}}]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo takiego wektora, albo
                odpowiedź ma nierozpoznany kształt
        """
        body = await self._client.request(
            "POST",
            f"{self._path}/points/query/groups",
            json={
                "query":        vector,
                "using":        vector_name,
                "group_by":     group_by,
                "group_size":   1,      # z grupy tylko najbliższy punkt
                "limit":        limit,  # liczba grup
                "with_payload": True,
            },
        )

        result = body.get("result")
        groups = result.get("groups") if isinstance(result, dict) else None

        if not isinstance(groups, list):
            raise DbQdrantError(
                f"Qdrant oddał nierozpoznany wynik wyszukiwania grup w kolekcji '{self._name}'"
            )

        # Grupa bez punktów nie ma czego oddać; Qdrant takich nie zwraca, ale kształt jest jego.
        entries = [group["hits"][0] for group in groups if group.get("hits")]

        logger.info(
            "search collection=%s using=%s group_by=%s limit=%d groups=%d",
            self._name,
            vector_name,
            group_by,
            limit,
            len(entries),
        )

        return entries

    async def _read_by_id(
        self,
        point_ids: Sequence[str],  # np. ["df3b51f3-…", "8c1e…"]
    ) -> list[dict]:
        """
        Description:
        Oddaje punkty o podanych identyfikatorach, z payloadem i wektorami, w kolejności
        identyfikatorów. Identyfikatora, którego w kolekcji nie ma, po prostu nie ma w wyniku —
        o tym, czy brak jest błędem, rozstrzyga wołający.

        Example args:
            point_ids=["df3b51f3-9eac-56f3-9f28-6253f23dd731"]

        Example result:
            [{"id": "df3b51f3-…", "vector": {"problem": […], "sts": […]}, "payload": {…}}]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo odpowiedź ma
                nierozpoznany kształt
        """
        # Bez powtórzeń, w kolejności podania.
        wanted = list(dict.fromkeys(point_ids))

        # --- nic do odczytania ---
        if not wanted:
            return []

        body    = await self._client.request(
            "POST",
            f"{self._path}/points",
            json={"ids": wanted, "with_payload": True, "with_vector": True},
        )
        entries = body.get("result")

        if not isinstance(entries, list):
            raise DbQdrantError(
                f"Qdrant oddał nierozpoznany wynik odczytu z kolekcji '{self._name}'"
            )

        # Qdrant nie obiecuje kolejności, więc układamy po identyfikatorach z zapytania.
        found  = {str(entry.get("id")): entry for entry in entries}
        points = [found[point_id] for point_id in wanted if point_id in found]

        logger.info(
            "read collection=%s asked=%d found=%d", self._name, len(wanted), len(points)
        )

        return points

    def _verify_schema(
        self,
        description: dict,  # np. {"result": {"config": {"params": {"vectors": {…}}}}}
    ) -> None:
        """
        Description:
        Sprawdza istniejącą kolekcję wobec schematu, z którym mamy do niej pisać: każdy nazwany
        wektor podklasy musi być i mieć wymiar podany przy budowie. Bez tego rozjazd wychodzi
        jako punkty odrzucone w środku przebiegu indeksacji.

        Example args:
            description={"result": {"config": {"params": {"vectors": {"problem": {"size": 768}}}}}}

        Example result:
            None — kolekcja się zgadza

        Raises:
            DbQdrantConfigError: brakuje nazwanego wektora albo ma inny wymiar
        """
        # Wartości domyślne zamiast indeksowania: nierozpoznany kształt ma dać NASZ komunikat
        # z nazwą kolekcji, a nie `KeyError` z trzeciego poziomu.
        vectors = (
            description.get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
        )

        for name in self.VECTORS:
            declared = vectors.get(name)

            # --- kolekcja zbudowana w innym układzie ---
            if declared is None:
                raise DbQdrantConfigError(
                    f"kolekcja '{self._name}' nie ma nazwanego wektora '{name}' "
                    f"(ma: {', '.join(sorted(vectors)) or 'brak'}) — skasuj ją i odbuduj z plików"
                )

            actual = declared.get("size")

            # --- kolekcja zbudowana pod inny model ---
            if actual != self._vector_size:
                raise DbQdrantConfigError(
                    f"kolekcja '{self._name}' ma wektor '{name}' o wymiarze {actual}, "
                    f"a EMBEDDING_VECTOR_SIZE={self._vector_size} — zmiana modelu wymaga NOWEJ "
                    f"kolekcji, nie migracji"
                )

        return None
