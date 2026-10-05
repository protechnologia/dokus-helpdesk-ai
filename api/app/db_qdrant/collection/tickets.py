"""
Description:
Kolekcja zgłoszeń w Qdrancie. Punkt to jedna karta zgłoszenia (`ParsedTicket`) z dwoma nazwanymi
wektorami; po wektorach `problem` szuka się zgłoszeń o podobnym problemie.

Baza wektorowa trzyma karty zgłoszeń, Postgres — oryginalne wątki. Ten sam numer zgłoszenia
wskazuje oba.

O czym pamiętać przy zmianach:

- Schemat kolekcji to `VECTORS` w klasie niżej i wymiar z konfiguracji. Zmiana nazw albo wymiaru
  nie dociera do istniejącej kolekcji: `ensure()` jej nie naprawia, tylko odmawia, a kolekcję
  kasuje się i odbudowuje z `data/unsafe/parsed/` (`helpdesk rag reindex`).
- Nazwa wektora przy szukaniu jest argumentem wymaganym, bez wartości domyślnej. Kolekcja ma dwie
  przestrzenie, a szukanie po niewłaściwej nie jest błędem, tylko daje trochę gorsze wyniki —
  wartość domyślna pozwoliłaby trafić tam przez zapomnienie.
- Wołający podaje numery zgłoszeń; identyfikatory punktów liczy kolekcja.
"""

from collections.abc import Sequence

from app.db_qdrant.collection.base import VectorCollection
from app.db_qdrant.hit.tickets import TicketHit
from app.db_qdrant.point.base import point_id_for
from app.db_qdrant.point.tickets import VECTOR_PROBLEM, VECTOR_STS, TicketPoint


class TicketsCollection(VectorCollection):
    """
    Description:
    Kolekcja zgłoszeń: zakładanie, zapis kart, szukanie po wektorze i odczyt po numerze.

    Do czego:
    Stąd `find_tickets_vector` bierze zgłoszenia o podobnym problemie, a indeksacja
    (`TicketsIndexer`) tu je zapisuje. Odczyt po numerze daje kartę zgłoszenia znalezionego inną
    drogą, np. wątku z wyszukiwania tekstowego. Mechanika żądań stoi w klasie bazowej.

    Flow:
        1. Indeksacja: `ensure()` z klasy bazowej, potem `upsert()`; przebudowa zaczyna od
           `drop()`.
        2. Narzędzie: `search()` → trafienia `TicketHit`, od najbardziej podobnego.
        3. Odczyt: `read_by_id()` → punkty `TicketPoint` o podanych numerach zgłoszeń.
    """

    # Nazwane wektory kolekcji zgłoszeń — jej cały schemat poza wymiarem z konfiguracji.
    VECTORS = (VECTOR_PROBLEM, VECTOR_STS)

    async def upsert(
        self,
        points: Sequence[TicketPoint],  # np. [TicketPoint.from_ticket(ticket, […], […])]
    ) -> int:
        """
        Description:
        Zapisuje zgłoszenia i oddaje, ile zapisano. Punkt tego samego zgłoszenia jest
        nadpisywany, więc ponowna indeksacja nie dubluje korpusu.

        Example args:
            points=[TicketPoint(point_id="df3b51f3-…", payload={"ticket_id": "33644", …}, …)]

        Example result:
            1

        Raises:
            DbQdrantError: Qdrant nie odpowiedział albo odrzucił zapis
        """
        written = await self._upsert([point.to_qdrant() for point in points])

        return written

    async def search(
        self,
        vector:      list[float],  # np. [0.0123, -0.0456] — z embed_query()
        vector_name: str,          # np. VECTOR_PROBLEM — w której przestrzeni szukać
        limit:       int,          # np. 5 — RAG_TOP_K
    ) -> list[TicketHit]:
        """
        Description:
        Znajduje `limit` zgłoszeń najbliższych wektorowi w podanej przestrzeni, od najbardziej
        podobnego.

        Example args:
            vector=[0.0123, -0.0456]
            vector_name=VECTOR_PROBLEM
            limit=5

        Example result:
            [TicketHit(point_id="df3b51f3-…", score=0.87, payload={"ticket_id": "33644", …})]

        Raises:
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo takiego wektora, albo
                odpowiedź ma nierozpoznany kształt
        """
        entries = await self._search(vector=vector, vector_name=vector_name, limit=limit)
        hits    = [TicketHit.from_qdrant(entry) for entry in entries]

        return hits

    async def read_by_id(
        self,
        ticket_ids: Sequence[str],  # np. ["33644", "10718"]
    ) -> list[TicketPoint]:
        """
        Description:
        Oddaje zgłoszenia o podanych numerach, w kolejności numerów — całe punkty, z kartą
        i wektorami. Numeru, którego w kolekcji nie ma, po prostu nie ma w wyniku.

        Example args:
            ticket_ids=["33644", "10718"]

        Example result:
            [TicketPoint(point_id="df3b51f3-…", payload={"ticket_id": "33644", …}, …)]

        Raises:
            DbQdrantConfigError: punkt nie ma któregoś z nazwanych wektorów
            DbQdrantError: Qdrant nie odpowiedział, nie ma kolekcji albo odpowiedź ma
                nierozpoznany kształt
        """
        point_ids = [point_id_for(ticket_id) for ticket_id in ticket_ids]
        entries   = await self._read_by_id(point_ids)
        points    = [TicketPoint.from_qdrant(entry) for entry in entries]

        return points
