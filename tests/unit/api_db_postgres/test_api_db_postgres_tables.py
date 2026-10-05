from datetime import date

import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.tickets.fake_tickets import SIGNING_THREAD
from app.db_postgres import DbPostgresConfigError, DocRow, DocsTable, TicketRow, TicketsTable
from app.db_postgres.table.base import WHITESPACE_RUN

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
        self.closed = False

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

    async def aclose(self) -> None:
        """
        Description:
        Zapisuje, że klient został zamknięty.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True


# --- nazwa i zakładanie tabeli ---


def test_each_material_has_its_own_table() -> None:
    """Sprawdza, czy tabela zgłoszeń i tabela dokumentacji mają różne nazwy domyślne: `tickets_text`
    i `docs_text`.

    Wyłapuje pomyłkę, po której oba materiały trafiłyby do jednej tabeli: wyszukiwanie
    w zgłoszeniach oddawałoby wtedy sekcje dokumentacji i odwrotnie."""
    assert TicketsTable(StubClient()).name == "tickets_text"
    assert DocsTable(StubClient()).name    == "docs_text"


@pytest.mark.parametrize(
    "name",
    ["", "Docs", "docs text", 'docs"; DROP TABLE x; --', "1docs", "docs-text"],
    ids=["pusta", "wielka litera", "spacja", "wstrzyknięcie", "od cyfry", "łącznik"],
)
def test_a_table_name_outside_the_pattern_is_refused(name: str) -> None:
    """Sprawdza, czy tabela odmawia niedozwolonej nazwy już przy budowie: nazwa pusta, z wielką
    literą, spacją albo łącznikiem, zaczynająca się od cyfry lub niosąca fragment SQL-a kończy się
    wyjątkiem `DbPostgresConfigError`.

    Wyłapuje poluzowanie wzorca nazwy. Nazwa tabeli to jedyna wartość z zewnątrz wstawiana wprost
    w treść SQL-a, więc przepuszczona bez kontroli mogłaby dopisać do zapytania własne polecenie."""
    with pytest.raises(DbPostgresConfigError):
        TicketsTable(StubClient(), name=name)


async def test_the_table_is_created_with_its_searched_text_and_index() -> None:
    """Sprawdza, czy zakładanie tabeli dokumentacji wysyła do bazy, po sprawdzeniu konfiguracji
    wyszukiwania, jedno polecenie: tabelę `docs_text`, przeszukiwany tekst i wektor słów złożone
    z tytułu i treści sekcji oraz indeks `docs_text_search` na wektorze słów.

    Wyłapuje polecenie, w którym nazwa tabeli nie została podstawiona, brakuje indeksu albo
    przeszukiwany tekst powstaje z innych kolumn niż tytuł i treść, na przykład także z opisu
    sekcji, który pisze model, a nie autor dokumentacji."""
    client = StubClient()

    await DocsTable(client).create()

    create = client.calls[1][0]

    assert len(client.calls) == 2
    assert 'CREATE TABLE IF NOT EXISTS "docs_text"' in create
    assert "regexp_replace(title || E'\\n' || body, " in create
    assert "to_tsvector('pl_search', title || E'\\n' || body)" in create
    assert 'CREATE INDEX IF NOT EXISTS "docs_text_search" ON "docs_text" USING gin' in create


@pytest.mark.parametrize("table_class", TABLES)
async def test_the_searched_text_and_the_query_collapse_whitespace_the_same_way(
    table_class: type,
) -> None:
    """Sprawdza, czy w obu tabelach przeszukiwany tekst (kolumna `search_text`) i zapytanie
    szukające dosłownego ciągu zamieniają każdy ciąg odstępów na jedną spację tym samym wzorcem,
    `WHITESPACE_RUN`.

    Wyłapuje wzorzec zmieniony tylko po jednej stronie, na przykład w samym pliku `_create.sql`.
    Komunikat złamany w źródle między liniami da się znaleźć tylko wtedy, gdy tekst i zapytanie
    rozumieją „odstęp" tak samo."""
    creating  = StubClient()
    searching = StubClient()

    await table_class(creating).create()
    await table_class(searching).substring("Zaloguj się\nponownie")

    collapse = f"'{WHITESPACE_RUN}', ' ', 'g')"

    assert collapse in creating.calls[1][0]
    assert collapse in searching.calls[0][0]


async def test_a_database_without_the_search_configuration_gets_no_table() -> None:
    """Sprawdza, czy w bazie bez konfiguracji wyszukiwania `pl_search` zakładanie tabeli kończy się
    wyjątkiem `DbPostgresConfigError`, który wskazuje wolumen `postgres_data` do odtworzenia, i czy
    poza samym sprawdzeniem do bazy nie idzie wtedy żadne polecenie.

    Wyłapuje zakładanie tabeli bez tego sprawdzenia: baza ze starszego wolumenu odpowiada poprawnie,
    ale konfiguracji nie ma, więc zakładanie kończyłoby się błędem serwera, który nie mówi, co
    naprawić."""
    client = StubClient(value=0)

    with pytest.raises(DbPostgresConfigError, match="postgres_data"):
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
    """Sprawdza, czy szukanie po słowach i po frazie w obu tabelach pyta o zapisany wektor słów
    właściwej tabeli, a tekst zapytania (tu z apostrofem i średnikiem) idzie do bazy jako osobna
    wartość, nie jako część SQL-a. Sprawdza też, że zapytanie nie ma limitu wyników.

    Wyłapuje sklejanie tekstu agenta z treścią SQL-a, czyli furtkę do wstrzyknięcia polecenia, oraz
    dopisany limit: narzędzie musi wiedzieć, ile wierszy pasowało w sumie, żeby policzyć
    pominięte."""
    client = StubClient()
    table  = table_class(client)

    await getattr(table, method)("serwer'; --")

    sql, *values = client.calls[0]

    assert function in sql
    assert f'FROM "{table.name}"' in sql
    assert values == ["serwer'; --"]
    assert "serwer" not in sql
    assert "LIMIT"  not in sql


@pytest.mark.parametrize(
    ("table_class", "order"),
    [(TicketsTable, "ticket_date DESC, ticket_id DESC"), (DocsTable, "section_id")],
)
async def test_each_table_orders_what_it_finds_its_own_way(
    table_class: type,
    order:       str,
) -> None:
    """Sprawdza, czy każda tabela układa trafienia po swojemu: zgłoszenia od najnowszych, sekcje
    dokumentacji według identyfikatora. Przy szukaniu dosłownego ciągu to cała kolejność, a przy
    szukaniu po słowach pierwsza jest trafność i dopiero remisy rozstrzyga kolejność tabeli.

    Wyłapuje zapytanie, które gubi tę kolejność albo stawia ją przed trafnością. Gdy pasuje więcej
    zgłoszeń, niż narzędzie pokazuje, mają zostać najświeższe, bo nowsze zgłoszenie bywa poprawką
    starszego."""
    client = StubClient()
    table  = table_class(client)

    await table.substring("x")
    await table.words("x")

    substring_sql = client.calls[0][0]
    words_sql     = client.calls[1][0]

    assert substring_sql.endswith(f"ORDER BY {order}")
    assert "ORDER BY ts_rank(" in words_sql
    assert words_sql.endswith(f"DESC, {order}")


async def test_a_substring_query_is_escaped_before_it_is_sent() -> None:
    """Sprawdza, czy przy szukaniu dosłownego ciągu znaki `%` i `_` z zapytania („100%_gotowe") idą
    do bazy poprzedzone znakiem ucieczki, a warunek szuka w kolumnie `search_text`.

    Wyłapuje zapytanie wysłane bez tej poprawki: baza czyta `%` jako „dowolny ciąg", a `_` jako
    „dowolny znak", więc komunikat błędu z takim znakiem pasowałby do tekstów, które go wcale nie
    zawierają."""
    client = StubClient()

    await TicketsTable(client).substring("100%_gotowe")

    sql, *values = client.calls[0]

    assert "search_text ILIKE" in sql and "ESCAPE" in sql
    assert values == ["100\\%\\_gotowe"]


# --- zapis i odczyt wierszy ---


async def test_rows_are_written_in_one_statement_column_by_column() -> None:
    """Sprawdza, czy zapis zgłoszeń idzie do bazy jednym poleceniem, które istniejący numer
    nadpisuje, z osobną listą wartości na każdą kolumnę, w kolejności pól wiersza, i czy zapis
    pustej listy w ogóle nie woła bazy.

    Wyłapuje zapis, w którym wartości trafiają do nie swoich kolumn (na przykład temat w miejsce
    wątku), oraz taki, który przy powtórzonym numerze nie nadpisuje wiersza. Ponowna indeksacja ma
    zastępować zgłoszenia, nie dokładać ich ani kończyć się błędem."""
    client = StubClient()

    await TicketsTable(client).upsert([])
    await TicketsTable(client).upsert([TICKET_ROW])

    sql, *arrays = client.calls[0]

    assert len(client.calls) == 1
    assert 'INSERT INTO "tickets_text"' in sql and "ON CONFLICT (ticket_id) DO UPDATE" in sql
    assert arrays == [[value] for value in TICKET_ROW.model_dump().values()]


@pytest.mark.parametrize(
    ("table_class", "key"),
    [(TicketsTable, "ticket_id"), (DocsTable, "section_id")],
)
@pytest.mark.parametrize("method", ["words", "phrase", "substring"])
async def test_a_search_gives_back_the_keys_of_what_matched(
    table_class: type,
    key:         str,
    method:      str,
) -> None:
    """Sprawdza, czy każda z trzech dróg szukania (słowa, fraza, dosłowny ciąg) w obu tabelach
    oddaje same identyfikatory pasujących wierszy, w kolejności podanej przez bazę, a gdy nic nie
    pasuje, pustą listę. Zapytanie pobiera z bazy tylko kolumnę identyfikatora.

    Wyłapuje szukanie, które zmienia kolejność trafień, kończy się błędem przy braku wyników albo
    ściąga z bazy całe wiersze: szukanie ma mówić tylko, co pasuje, a treść daje dopiero odczyt."""
    stored = StubClient(rows=[{key: "pierwszy"}, {key: "drugi"}])

    found   = await getattr(table_class(stored), method)("x")
    nothing = await getattr(table_class(StubClient()), method)("x")

    assert found   == ["pierwszy", "drugi"]
    assert nothing == []
    assert stored.calls[0][0].startswith(f'SELECT {key} FROM "{table_class(stored).name}"')


async def test_rows_read_by_id_come_back_without_the_searched_columns() -> None:
    """Sprawdza, czy odczyt zgłoszenia po numerze oddaje wiersz z tymi samymi polami, które
    zapisano, choć baza dokłada do niego dwie kolumny wyliczane, służące tylko do szukania
    (`search_text` i `search_vector`).

    Wyłapuje odczyt, który tych dwóch kolumn nie odcina: model wiersza nie przyjmuje nieznanych pól,
    więc każdy odczyt wątku kończyłby się błędem."""
    record = {**TICKET_ROW.model_dump(), "search_text": "…", "search_vector": "'przesyłka':4"}

    found = await TicketsTable(StubClient(rows=[record])).read_by_id(["90011"])

    assert found == [TICKET_ROW]


async def test_tickets_are_read_by_their_numbers() -> None:
    """Sprawdza, czy odczyt zgłoszeń po dwóch numerach wysyła do bazy jedno zapytanie z oboma
    numerami jako jedną listą, każe ułożyć wynik w kolejności tej listy i oddaje wiersz z pełnym
    wątkiem.

    Wyłapuje odczyt, który pyta bazę osobno o każdy numer albo zostawia kolejność wyniku
    przypadkowi: wołający dostawałby wtedy zgłoszenia w innej kolejności, niż o nie prosił."""
    client = StubClient(rows=[TICKET_ROW.model_dump()])

    found = await TicketsTable(client).read_by_id(["90011", "90012"])

    sql, ids = client.calls[0]

    assert found == [TICKET_ROW]
    assert ids   == ["90011", "90012"]
    assert "ticket_id = ANY($1::text[])" in sql and "array_position($1::text[], ticket_id)" in sql


async def test_sections_are_listed_in_the_order_of_the_documents() -> None:
    """Sprawdza, czy spis sekcji dokumentacji prosi bazę o kolejność: dokument, wydanie, miejsce
    sekcji w dokumencie, i oddaje wiersz z bazy bez zmian.

    Wyłapuje spis bez ustalonej kolejności albo ułożony inaczej: agent dostałby spis treści,
    w którym sekcje różnych dokumentów są przemieszane albo nie stoją po kolei."""
    client = StubClient(rows=[DOC_ROW.model_dump()])

    listed = await DocsTable(client).list_all()

    assert listed == [DOC_ROW]
    assert "ORDER BY document, version, ordinal" in client.calls[0][0]


@pytest.mark.parametrize("table", TABLES)
async def test_aclose_closes_the_client_the_table_stands_on(table: type) -> None:
    """Sprawdza, czy `aclose()` wywołane na tabeli zgłoszeń albo dokumentacji zamyka klienta bazy,
    na którym ta tabela stoi.

    Wyłapuje `aclose()`, które nic nie robi: kto dostał samą tabelę, bez klienta, nie miałby wtedy
    jak zamknąć połączeń z bazą po skończonej pracy."""
    client = StubClient()

    await table(client).aclose()

    assert client.closed
