from datetime import date

import pytest

from app.db import DbConfigError, DocRow, DocsTable, TicketRow, TicketsTable
from app.tools.docs.fake_docs import default_sections
from app.tools.tickets.find_tickets_text.fake import SIGNING_THREAD

# Tabele testowane bez bazy, na kliencie-atrapie zapisującym SQL i wartości: sprawdzamy, CO idzie
# do bazy i jak czytamy odpowiedź. Że Postgres odpowiada na to tak, jak zakładamy, sprawdza test
# na stacku.

TABLES = [TicketsTable, DocsTable]

TICKET_ROW = TicketRow.from_thread("90011", date(2026, 3, 2), SIGNING_THREAD)
DOC_ROW    = DocRow.from_section(default_sections()[0], body="Uprawnienie nadaje…", ordinal=0)


class StubClient:
    """
    Description:
    Klient bez bazy: zapisuje każde zapytanie i oddaje ustalone wiersze albo wartość.
    """

    database = "helpdesk"

    def __init__(
        self,
        rows:  list[dict] | None = None,  # np. [TICKET_ROW.model_dump()]
        value: object = 1,                # np. 0 — baza bez konfiguracji wyszukiwania
    ):
        """
        Description:
        Ustala odpowiedzi klienta i zakłada dziennik zapytań.

        Example args:
            rows=[TICKET_ROW.model_dump()]
            value=1

        Example result:
            StubClient oddający jeden wiersz na każde `fetch_rows`
        """
        self._rows  = rows or []
        self._value = value

        self.calls: list[tuple] = []

    async def fetch_rows(self, sql: str, *args: object) -> list[dict]:
        """
        Description:
        Zapisuje zapytanie i oddaje ustalone wiersze.

        Example args:
            sql='SELECT section_id, … FROM "docs_text" …'
            args=("serwer", 5)

        Example result:
            [{"section_id": "adm-kancelaria-edoreczenia", …}]
        """
        self.calls.append((sql, *args))

        return self._rows

    async def fetch_value(self, sql: str, *args: object) -> object:
        """
        Description:
        Zapisuje zapytanie i oddaje ustaloną wartość.

        Example args:
            sql="SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"
            args=("pl_search",)

        Example result:
            1
        """
        self.calls.append((sql, *args))

        return self._value

    async def execute(self, sql: str, *args: object) -> None:
        """
        Description:
        Zapisuje polecenie.

        Example args:
            sql='DROP TABLE IF EXISTS "docs_text"'
            args=()

        Example result:
            None
        """
        self.calls.append((sql, *args))


# --- nazwa i zakładanie tabeli ---


def test_each_material_has_its_own_table() -> None:
    """Tabela zgłoszeń i tabela dokumentacji → różne nazwy domyślne: materiały się nie mieszają."""
    assert TicketsTable(StubClient()).name == "tickets_text"
    assert DocsTable(StubClient()).name    == "docs_text"


@pytest.mark.parametrize(
    "name",
    ["", "Docs", "docs text", 'docs"; DROP TABLE x; --', "1docs", "docs-text"],
    ids=["pusta", "wielka litera", "spacja", "wstrzyknięcie", "od cyfry", "łącznik"],
)
def test_a_table_name_outside_the_pattern_is_refused(name: str) -> None:
    """Nazwa tabeli spoza wzorca → DbConfigError przy budowie: to jedyna wartość z zewnątrz
    wstawiana w treść SQL-a."""
    with pytest.raises(DbConfigError):
        TicketsTable(StubClient(), name=name)


async def test_the_table_is_created_with_its_searched_text_and_index() -> None:
    """Zakładanie tabeli → jedno polecenie z `_create.sql`: tabela pod swoją nazwą, przeszukiwany
    tekst złączony z tytułu i treści oraz indeks na wektorze słów."""
    client = StubClient()

    await DocsTable(client).create()

    create = client.calls[1][0]

    assert len(client.calls) == 2
    assert 'CREATE TABLE IF NOT EXISTS "docs_text"' in create
    assert "search_text text GENERATED ALWAYS AS (title || E'\\n' || body) STORED" in create
    assert "to_tsvector('pl_search', title || E'\\n' || body)" in create
    assert 'CREATE INDEX IF NOT EXISTS "docs_text_search" ON "docs_text" USING gin' in create


async def test_a_database_without_the_search_configuration_gets_no_table() -> None:
    """Baza bez konfiguracji `pl_search` → DbConfigError mówiący, co zrobić, i żadnego polecenia
    zakładającego tabelę."""
    client = StubClient(value=0)

    with pytest.raises(DbConfigError, match="postgres_data"):
        await DocsTable(client).create()

    assert len(client.calls) == 1


# --- szukanie ---


@pytest.mark.parametrize("table_class", TABLES)
@pytest.mark.parametrize(
    ("method", "function"),
    [
        ("words",  "search_vector @@ plainto_tsquery('pl_search', $1)"),
        ("phrase", "search_vector @@ phraseto_tsquery('pl_search', $1)"),
    ],
)
async def test_words_and_phrases_use_the_stored_vector(
    table_class: type,
    method:      str,
    function:    str,
) -> None:
    """Słowa i fraza → warunek na zapisanym wektorze słów tabeli tego materiału; zapytanie agenta
    i limit idą parametrami, w treści SQL-a jest tylko nazwa tabeli."""
    client = StubClient()
    table  = table_class(client)

    await getattr(table, method)("serwer'; --", limit=5)

    sql, *values = client.calls[0]

    assert function in sql
    assert f'FROM "{table.name}"' in sql
    assert values == ["serwer'; --", 5]
    assert "serwer" not in sql


async def test_a_substring_query_is_escaped_before_it_is_sent() -> None:
    """Zapytanie do podciągu ze znakami `%` i `_` → do bazy idą unieszkodliwione, a warunek stoi
    na złączonym tekście: komunikat błędu ma być szukany dosłownie."""
    client = StubClient()

    await TicketsTable(client).substring("100%_gotowe", limit=5)

    sql, *values = client.calls[0]

    assert "search_text ILIKE" in sql and "ESCAPE" in sql
    assert values == ["100\\%\\_gotowe", 5]


# --- zapis i odczyt wierszy ---


async def test_rows_are_written_in_one_statement_column_by_column() -> None:
    """Zapis wierszy → jedno polecenie, lista wartości na kolumnę, w kolejności kolumn tabeli;
    pusty zapis nie woła bazy."""
    client = StubClient()

    await TicketsTable(client).upsert([])
    await TicketsTable(client).upsert([TICKET_ROW])

    sql, *arrays = client.calls[0]

    assert len(client.calls) == 1
    assert 'INSERT INTO "tickets_text"' in sql and "ON CONFLICT (ticket_id) DO UPDATE" in sql
    assert arrays == [[value] for value in TICKET_ROW.model_dump().values()]


@pytest.mark.parametrize("method", ["words", "phrase", "substring"])
async def test_found_tickets_come_back_as_rows(method: str) -> None:
    """Wiersze z bazy → `TicketRow` z tymi samymi polami, bez kolumn wyliczanych, które baza
    oddaje razem z wierszem; brak wierszy → pusta lista."""
    record = {**TICKET_ROW.model_dump(), "search_text": "…", "search_vector": "'przesyłka':4"}
    stored = StubClient(rows=[record])

    found   = await getattr(TicketsTable(stored), method)("x", limit=5)
    nothing = await getattr(TicketsTable(StubClient()), method)("x", limit=5)

    assert found   == [TICKET_ROW]
    assert nothing == []


async def test_tickets_are_read_by_their_numbers() -> None:
    """Odczyt po numerach → wiersze z pełnym wątkiem; numery idą jedną listą, a kolejność wyniku
    to kolejność numerów."""
    client = StubClient(rows=[TICKET_ROW.model_dump()])

    found = await TicketsTable(client).read_by_id(["90011", "90012"])

    sql, ids = client.calls[0]

    assert found == [TICKET_ROW]
    assert ids   == ["90011", "90012"]
    assert "ticket_id = ANY($1::text[])" in sql and "array_position($1::text[], ticket_id)" in sql


async def test_sections_are_listed_in_the_order_of_the_documents() -> None:
    """Spis treści → wiersze w kolejności: dokument, wydanie, miejsce sekcji w dokumencie."""
    client = StubClient(rows=[DOC_ROW.model_dump()])

    listed = await DocsTable(client).list_all()

    assert listed == [DOC_ROW]
    assert "ORDER BY document, version, ordinal" in client.calls[0][0]
