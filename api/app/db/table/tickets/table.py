"""
Description:
Tabela wyszukiwania tekstowego zgłoszeń. Wiersz to jedno zgłoszenie w oryginalnym brzmieniu:
numer, data, temat i pełny tekst wątku PO ANONIMIZACJI. Kolumny i indeks widać wprost
w `_create.sql` obok.

Baza wektorowa trzyma karty zgłoszeń, ta tabela — oryginały. Karty tu nie ma i nie szuka się
po niej: trafienie ma być trafieniem w to, co napisano w zgłoszeniu, a nie w słowa parsera.

O czym pamiętać przy zmianach:

- Kolumna dopisana do `_create.sql` musi trafić też do `_upsert.sql` i do `TicketRow`, w tej samej
  kolejności. Rozjazd łapie test na stacku: zapis i odczyt tego samego wiersza.
- Tabela nie zależy od parsowania: powstaje z samych zgłoszeń po anonimizacji.
- Surowy wątek tu nie trafia — tylko tekst po anonimizacji, także temat.
- Zmiana kolumn nie dociera do istniejącej tabeli: `CREATE TABLE IF NOT EXISTS` jej nie rusza.
  Tabelę kasuje się i odbudowuje z plików.
"""

from collections.abc import Sequence
from pathlib import Path

from app.db.client import PostgresClient
from app.db.row.tickets import TicketRow
from app.db.table.base import TextTable

# Domyślna nazwa tabeli wyszukiwania zgłoszeń.
TICKETS_TABLE = "tickets_text"

KEY = "ticket_id"

# SQL tej tabeli leży obok, w plikach — tam widać kolumny, indeks i zapis.
SQL_DIR = Path(__file__).parent
CREATE  = (SQL_DIR / "_create.sql").read_text(encoding="utf-8")  # tabela i jej indeks
UPSERT  = (SQL_DIR / "_upsert.sql").read_text(encoding="utf-8")  # zapis wierszy


class TicketsTable(TextTable):
    """
    Description:
    Tabela wyszukiwania tekstowego zgłoszeń: zapis, szukanie w tekście wątku i odczyt po numerze.

    Do czego:
    Stąd `find_tickets_text` bierze zgłoszenia pasujące dosłownie do kodu błędu, komunikatu albo
    słów kluczowych — jako wiersze z oryginalnym wątkiem. Odczyt po numerze daje wątek
    zgłoszenia znalezionego inną drogą, np. karty z bazy wektorowej. Szukanie i odczyt to
    mechanika klasy bazowej; SQL zakładania i zapisu leży obok, w plikach `.sql`.

    Flow:
        1. Indeksacja: `create()`, potem `upsert()` (p. 31, p. 53).
        2. Narzędzie: `words()`, `phrase()` albo `substring()` → wiersze `TicketRow`.
        3. Odczyt: `read_by_id()` → wiersze o podanych numerach.
    """

    def __init__(
        self,
        client: PostgresClient,       # np. PostgresClient(host="postgres", …)
        name:   str = TICKETS_TABLE,  # inna nazwa tylko w testach — własna tabela testu
    ):
        """
        Description:
        Buduje tabelę zgłoszeń na podanym kliencie.

        Example args:
            client=PostgresClient(host="postgres", port=5432, database="helpdesk", …)
            name="tickets_text"

        Example result:
            TicketsTable „tickets_text"

        Raises:
            DbConfigError: niedozwolona nazwa tabeli
        """
        super().__init__(client, name)

    async def create(self) -> None:
        """
        Description:
        Zakłada tabelę zgłoszeń i jej indeks pełnotekstowy, jeśli ich nie ma.

        Example args:
            (brak)

        Example result:
            None — tabela istnieje

        Raises:
            DbConfigError: w bazie nie ma konfiguracji `pl_search`
            DbError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        await self._require_search_config()

        await self._client.execute(CREATE.format(table=self._sql_name, name=self._name))

    async def upsert(
        self,
        rows: Sequence[TicketRow],  # np. [TicketRow.from_thread("90011", date(2026, 3, 2), "…")]
    ) -> None:
        """
        Description:
        Zapisuje zgłoszenia jednym poleceniem; istniejący numer dostaje nowe dane. Przeszukiwany
        tekst baza przelicza sama.

        Example args:
            rows=[TicketRow(ticket_id="90011", subject="Błąd przy podpisie", thread="…", …)]

        Example result:
            None

        Raises:
            DbError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        # --- nic do zapisania ---
        if not rows:
            return None

        # Lista wartości na kolumnę, w kolejności pól wiersza — tej samej co w `_upsert.sql`.
        values = [[getattr(row, field) for row in rows] for field in TicketRow.model_fields]

        await self._client.execute(UPSERT.format(table=self._sql_name), *values)

        return None

    async def read_by_id(
        self,
        ticket_ids: Sequence[str],  # np. ["90011", "90012"]
    ) -> list[TicketRow]:
        """
        Description:
        Oddaje zgłoszenia o podanych numerach, w kolejności numerów. Numeru, którego w tabeli
        nie ma, po prostu nie ma w wyniku.

        Example args:
            ticket_ids=["90011", "90012"]

        Example result:
            [TicketRow(ticket_id="90011", thread="…", …), TicketRow(ticket_id="90012", …)]

        Raises:
            DbError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._read_by_id(key=KEY, ids=ticket_ids)
        rows    = [TicketRow(**record) for record in records]

        return rows

    async def words(
        self,
        query: str,  # np. "załącznik limit"
        limit: int,  # np. 5
    ) -> list[TicketRow]:
        """
        Description:
        Znajduje zgłoszenia, których wątek zawiera wszystkie słowa zapytania — w dowolnej
        kolejności i odmianie.

        Example args:
            query="załącznik limit"
            limit=5

        Example result:
            [TicketRow(ticket_id="90003", subject="Brak przesyłek z e-Doręczeń", …)]

        Raises:
            DbError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_words(query=query, limit=limit, order=KEY)
        rows    = [TicketRow(**record) for record in records]

        return rows

    async def phrase(
        self,
        query: str,  # np. "nie udało się skomunikować z serwerem"
        limit: int,  # np. 5
    ) -> list[TicketRow]:
        """
        Description:
        Znajduje zgłoszenia zawierające słowa zapytania obok siebie, w tej samej kolejności —
        komunikat przepisany z ekranu.

        Example args:
            query="nie udało się skomunikować z serwerem"
            limit=5

        Example result:
            [TicketRow(ticket_id="90011", …), TicketRow(ticket_id="90012", …)]

        Raises:
            DbError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_phrase(query=query, limit=limit, order=KEY)
        rows    = [TicketRow(**record) for record in records]

        return rows

    async def substring(
        self,
        query: str,  # np. "ORA-00942"
        limit: int,  # np. 5
    ) -> list[TicketRow]:
        """
        Description:
        Znajduje zgłoszenia zawierające zapytanie dosłownie, bez względu na wielkość liter — kod
        błędu albo jego fragment.

        Example args:
            query="ORA-00942"
            limit=5

        Example result:
            [TicketRow(ticket_id="90014", subject="Błąd przy zapisie pisma", …)]

        Raises:
            DbError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_substring(query=query, limit=limit, order=KEY)
        rows    = [TicketRow(**record) for record in records]

        return rows
