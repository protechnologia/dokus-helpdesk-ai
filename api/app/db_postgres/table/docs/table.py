"""
Description:
Tabela wyszukiwania tekstowego dokumentacji. Wiersz to jedna sekcja: opis z metryczki, miejsce
w dokumencie i treść. Kolumny i indeks widać wprost w `_create.sql` obok.

Szuka się w tytule i w treści sekcji: baza łączy je w `search_text` i liczy z nich
`search_vector`. Opis z metryczki nie jest przeszukiwany — pisze go model przy przygotowaniu
plików, a trafienie ma wynikać z oryginału.

O czym pamiętać przy zmianach:

- Kolumna dopisana do `_create.sql` musi trafić też do `_upsert.sql` i do `DocRow`, w tej samej
  kolejności. Rozjazd łapie test na stacku: zapis i odczyt tego samego wiersza.
- `read_by_id()` nie zgłasza braku sekcji — oddaje te, które są. O tym, że brak to błąd,
  rozstrzyga narzędzie (`read_docs`: wszystko albo nic).
- Zmiana kolumn nie dociera do istniejącej tabeli: `CREATE TABLE IF NOT EXISTS` jej nie rusza.
  Tabelę kasuje się i odbudowuje z plików.
"""

from collections.abc import Sequence
from pathlib import Path

from app.db_postgres.client import PostgresClient
from app.db_postgres.row.docs import DocRow
from app.db_postgres.table.base import TextTable

# Domyślna nazwa tabeli wyszukiwania dokumentacji.
DOCS_TABLE = "docs_text"

KEY = "section_id"

# SQL tej tabeli leży obok, w plikach — tam widać kolumny, indeks i zapis.
SQL_DIR = Path(__file__).parent
CREATE  = (SQL_DIR / "_create.sql").read_text(encoding="utf-8")  # tabela i jej indeks
UPSERT  = (SQL_DIR / "_upsert.sql").read_text(encoding="utf-8")  # zapis wierszy

# Kolejność spisu treści: dokument po dokumencie, sekcje w kolejności z metryczki.
LISTING_ORDER = "document, version, ordinal"


class DocsTable(TextTable):
    """
    Description:
    Tabela wyszukiwania tekstowego dokumentacji: zapis sekcji, spis treści, szukanie po treści
    i odczyt sekcji.

    Do czego:
    Stąd czytają narzędzia dokumentacji: `list_docs` spis treści, `find_docs_text` sekcje
    pasujące dosłownie, `read_docs` treść. Szukanie i odczyt to mechanika klasy bazowej; SQL
    zakładania i zapisu leży obok, w plikach `.sql`.

    Flow:
        1. Import dokumentacji: `create()`, potem `upsert()` (p. 49).
        2. Narzędzia: `list_all()`, metody szukania, `read_by_id()` — wszystkie oddają `DocRow`.
    """

    def __init__(
        self,
        client: PostgresClient,    # np. PostgresClient(host="postgres", …)
        name:   str = DOCS_TABLE,  # inna nazwa tylko w testach — własna tabela testu
    ):
        """
        Description:
        Buduje tabelę dokumentacji na podanym kliencie.

        Example args:
            client=PostgresClient(host="postgres", port=5432, database="helpdesk", …)
            name="docs_text"

        Example result:
            DocsTable „docs_text"

        Raises:
            DbPostgresConfigError: niedozwolona nazwa tabeli
        """
        super().__init__(client, name)

    async def create(self) -> None:
        """
        Description:
        Zakłada tabelę dokumentacji i jej indeks pełnotekstowy, jeśli ich nie ma.

        Example args:
            (brak)

        Example result:
            None — tabela istnieje

        Raises:
            DbPostgresConfigError: w bazie nie ma konfiguracji `pl_search`
            DbPostgresError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        await self._require_search_config()

        await self._client.execute(CREATE.format(table=self._sql_name, name=self._name))

    async def upsert(
        self,
        rows: Sequence[DocRow],  # np. [DocRow.from_section(section, body="…", ordinal=0)]
    ) -> None:
        """
        Description:
        Zapisuje sekcje jednym poleceniem; istniejący identyfikator dostaje nowe dane.
        Przeszukiwany tekst baza przelicza sama.

        Example args:
            rows=[DocRow(section_id="adm-kancelaria-edoreczenia", ordinal=0, body="…", …)]

        Example result:
            None

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        # --- nic do zapisania ---
        if not rows:
            return None

        # Lista wartości na kolumnę, w kolejności pól wiersza — tej samej co w `_upsert.sql`.
        values = [[getattr(row, field) for row in rows] for field in DocRow.model_fields]

        await self._client.execute(UPSERT.format(table=self._sql_name), *values)

        return None

    async def list_all(self) -> list[DocRow]:
        """
        Description:
        Oddaje wszystkie sekcje w kolejności spisu treści: dokument po dokumencie, sekcje
        w kolejności z metryczki.

        Example args:
            (brak)

        Example result:
            [DocRow(section_id="adm-kancelaria-edoreczenia", ordinal=0, …), DocRow(…), …]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._list(order=LISTING_ORDER)
        rows    = [DocRow(**record) for record in records]

        return rows

    async def read_by_id(
        self,
        section_ids: Sequence[str],  # np. ["usr-wysylka-status-w-toku"]
    ) -> list[DocRow]:
        """
        Description:
        Oddaje sekcje o podanych identyfikatorach, w kolejności identyfikatorów. Identyfikatora,
        którego w tabeli nie ma, po prostu nie ma w wyniku.

        Example args:
            section_ids=["usr-wysylka-status-w-toku"]

        Example result:
            [DocRow(section_id="usr-wysylka-status-w-toku", body="Status „W toku”…", …)]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._read_by_id(key=KEY, ids=section_ids)
        rows    = [DocRow(**record) for record in records]

        return rows

    async def words(
        self,
        query: str,  # np. "uprawnienie kancelaria"
        limit: int,  # np. 5
    ) -> list[DocRow]:
        """
        Description:
        Znajduje sekcje zawierające wszystkie słowa zapytania — w dowolnej kolejności i odmianie,
        w tytule albo w treści.

        Example args:
            query="uprawnienie kancelaria"
            limit=5

        Example result:
            [DocRow(section_id="adm-kancelaria-edoreczenia", …), DocRow(…)]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_words(query=query, limit=limit, order=KEY)
        rows    = [DocRow(**record) for record in records]

        return rows

    async def phrase(
        self,
        query: str,  # np. "nie udało się skomunikować z serwerem"
        limit: int,  # np. 5
    ) -> list[DocRow]:
        """
        Description:
        Znajduje sekcje zawierające słowa zapytania obok siebie, w tej samej kolejności —
        komunikat albo nazwę opcji przepisaną z ekranu.

        Example args:
            query="nie udało się skomunikować z serwerem"
            limit=5

        Example result:
            [DocRow(section_id="usr-komunikat-brak-serwera", …)]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_phrase(query=query, limit=limit, order=KEY)
        rows    = [DocRow(**record) for record in records]

        return rows

    async def substring(
        self,
        query: str,  # np. "Ustawienia → Uprawnienia"
        limit: int,  # np. 5
    ) -> list[DocRow]:
        """
        Description:
        Znajduje sekcje zawierające zapytanie dosłownie, bez względu na wielkość liter — kod,
        ścieżkę w menu albo fragment komunikatu.

        Example args:
            query="Ustawienia → Uprawnienia"
            limit=5

        Example result:
            [DocRow(section_id="adm-kancelaria-edoreczenia", …), DocRow(…)]

        Raises:
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._find_substring(query=query, limit=limit, order=KEY)
        rows    = [DocRow(**record) for record in records]

        return rows
