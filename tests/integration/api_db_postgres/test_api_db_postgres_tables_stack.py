"""
Description:
Test integracyjny tabel Postgresa z prawdziwą bazą: czy to, co tabela zapisuje, wraca z niej
w tym samym kształcie, i czy szukanie widzi dokładnie ten tekst, który miało widzieć. Wymaga
działającego stacku.

| tabela         | scenariusz                             | oczekiwanie                            |
|----------------|----------------------------------------|----------------------------------------|
| `TicketsTable` | zapis i odczyt po numerach             | te same wiersze, w kolejności numerów  |
| `TicketsTable` | słowo z wątku w innej odmianie         | numer zgłoszenia                       |
| `TicketsTable` | fragment komunikatu z wątku            | numery znalezione podciągiem           |
| `DocsTable`    | zapis dwóch dokumentów i spis          | sekcje w kolejności dokumentów         |
| `DocsTable`    | odczyt po identyfikatorach             | sekcje z treścią, w kolejności żądania |
| `DocsTable`    | słowo z tytułu, słowo z opisu          | tytuł przeszukiwany, opis nie          |
| `DocsTable`    | komunikat złamany między liniami       | znaleziony podciągiem, treść dosłowna  |
| `DocsTable`    | twarda spacja w treści                 | znaleziona zwykłą spacją               |
| obie           | ponowny zapis tych samych wierszy      | bez duplikatów                         |

O czym pamiętać przy zmianach:

- Tabele są własne (`*_stack_test`), nigdy tabele narzędzi — test je zakłada i kasuje.
- Dane to zmyślone zestawy atrap narzędzi, nigdy korpus.
- SQL i tłumaczenie wierszy sprawdzają testy jednostkowe na kliencie-atrapie. Tu zostaje to,
  czego bez serwera nie da się dowieść: że Postgres przyjmuje te polecenia, sam przelicza
  przeszukiwany tekst i oddaje daty oraz liczby tak, jak zakładamy.
"""

from collections.abc import AsyncIterator

import pytest

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.tickets.fake_tickets import default_threads
from app.db_postgres import DocRow, DocsTable, PostgresClient, TicketsTable
from tests.conftest import build_postgres_client

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]

# Dwa zmyślone zgłoszenia ze wspólnego zestawu atrap narzędzi. „Załącznik" jest tylko w wątku
# pierwszego, komunikat błędu w obu.
ROWS = [row for row in default_threads() if row.ticket_id in ("90011", "90012")]

# Cztery zmyślone sekcje z dwóch dokumentów, z miejscem każdej w jej dokumencie.
SECTIONS = default_sections()
TEXTS    = default_texts()
DOC_ROWS = [
    DocRow.from_section(SECTIONS[0], body=TEXTS[SECTIONS[0].section_id], ordinal=0),
    DocRow.from_section(SECTIONS[1], body=TEXTS[SECTIONS[1].section_id], ordinal=1),
    DocRow.from_section(SECTIONS[2], body=TEXTS[SECTIONS[2].section_id], ordinal=0),
    DocRow.from_section(SECTIONS[3], body=TEXTS[SECTIONS[3].section_id], ordinal=1),
]


@pytest.fixture
async def client() -> AsyncIterator[PostgresClient]:
    """
    Description:
    Klient połączony z bazą na stacku, zamykany po teście.

    Example args:
        (brak)

    Example result:
        PostgresClient dla localhost:5433/helpdesk
    """
    client = build_postgres_client()

    yield client

    await client.aclose()


@pytest.fixture
async def tickets(client: PostgresClient) -> AsyncIterator[TicketsTable]:
    """
    Description:
    Własna tabela zgłoszeń testu z zapisanymi dwoma zmyślonymi zgłoszeniami — zakładana przed
    testem i kasowana po nim.

    Example args:
        client=PostgresClient(…)

    Example result:
        TicketsTable „tickets_text_stack_test" z dwoma zgłoszeniami
    """
    table = TicketsTable(client, name="tickets_text_stack_test")

    await table.drop()
    await table.create()
    await table.upsert(ROWS)

    yield table

    await table.drop()


@pytest.fixture
async def docs(client: PostgresClient) -> AsyncIterator[DocsTable]:
    """
    Description:
    Własna tabela dokumentacji testu z zapisanymi czterema zmyślonymi sekcjami — zapisanymi
    w odwrotnej kolejności, żeby spis treści nie mógł wyjść dobrze przypadkiem.

    Example args:
        client=PostgresClient(…)

    Example result:
        DocsTable „docs_text_stack_test" z czterema sekcjami
    """
    table = DocsTable(client, name="docs_text_stack_test")

    await table.drop()
    await table.create()
    await table.upsert(list(reversed(DOC_ROWS)))

    yield table

    await table.drop()


async def test_tickets_are_read_back_as_they_were_written(tickets: TicketsTable) -> None:
    """Zapis i odczyt po numerach → te same wiersze, z wątkiem, w kolejności numerów z żądania;
    nieznanego numeru w wyniku nie ma."""
    read = await tickets.read_by_id(["90012", "nie-ma-takiego", "90011"])

    assert read == [ROWS[1], ROWS[0]]


async def test_a_ticket_is_found_by_a_word_of_its_thread(tickets: TicketsTable) -> None:
    """Słowo z wątku w innej odmianie → to jedno zgłoszenie; słowo, którego nie ma w żadnym
    wątku → nic."""
    by_thread = await tickets.words("załączniki")
    nothing   = await tickets.words("hipopotam")

    assert by_thread == [ROWS[0].ticket_id]
    assert nothing   == []


async def test_a_message_is_found_as_a_substring_of_the_thread(tickets: TicketsTable) -> None:
    """Fragment komunikatu inną wielkością liter → oba zgłoszenia, w których wątku padł."""
    found = await tickets.substring("SKOMUNIKOWAĆ Z SERWEREM")

    assert found == [row.ticket_id for row in ROWS]


async def test_writing_the_same_tickets_twice_duplicates_nothing(tickets: TicketsTable) -> None:
    """Ten sam zapis drugi raz → nadal dwa zgłoszenia: ponowna indeksacja nadpisuje, nie dokłada."""
    await tickets.upsert(ROWS)

    found = await tickets.substring("skomunikować z serwerem")

    assert found == [row.ticket_id for row in ROWS]


async def test_the_listing_follows_the_documents(docs: DocsTable) -> None:
    """Sekcje zapisane w odwrotnej kolejności → spis treści dokument po dokumencie, sekcje według
    miejsca w dokumencie."""
    listed = await docs.list_all()

    assert listed == DOC_ROWS


async def test_sections_are_read_in_the_order_asked(docs: DocsTable) -> None:
    """Odczyt po identyfikatorach → sekcje z treścią w kolejności żądania; nieznanego
    identyfikatora w wyniku nie ma, o błędzie rozstrzyga narzędzie."""
    wanted = ["usr-wysylka-status-w-toku", "nie-ma-takiej", "adm-kancelaria-edoreczenia"]

    read = await docs.read_by_id(wanted)

    assert read == [DOC_ROWS[2], DOC_ROWS[0]]
    assert read[0].to_section() == SECTIONS[2]


async def test_the_title_is_searched_and_the_description_is_not(docs: DocsTable) -> None:
    """Słowo tylko z tytułu → sekcja znaleziona; słowo tylko z opisu z metryczki → nic: opis pisze
    model przy przygotowaniu plików, a trafienie ma wynikać z oryginału."""
    row = DocRow(
        section_id   = "probna-sekcja",
        ordinal      = 9,
        document     = "Dokument próbny",
        version      = "1",
        chapter_path = "[]",
        title        = "Sekcja o jednorożcach",
        description  = "Opis wspomina hipopotama",
        body         = "Treść mówi tylko o kancelarii.",
    )

    await docs.upsert([row])

    by_title       = await docs.words("jednorożec")
    by_description = await docs.words("hipopotam")

    assert by_title       == [row.section_id]
    assert by_description == []


def _probe_row(
    body: str,  # np. "Pojawia się komunikat „Zaloguj się\nponownie, aby kontynuować”."
) -> DocRow:
    """
    Description:
    Jedna zmyślona sekcja o podanej treści, do sprawdzenia, co widzi podciąg.

    Example args:
        body="Pojawia się komunikat „Zaloguj się\nponownie, aby kontynuować”."

    Example result:
        DocRow(section_id="probna-sekcja", body="Pojawia się komunikat…", …)
    """
    row = DocRow(
        section_id   = "probna-sekcja",
        ordinal      = 9,
        document     = "Dokument próbny",
        version      = "1",
        chapter_path = "[]",
        title        = "Sekcja próbna",
        description  = "Opis próbny",
        body         = body,
    )

    return row


async def test_a_message_broken_across_lines_is_found_and_the_body_stays_verbatim(
    docs: DocsTable,
) -> None:
    """Komunikat złamany w pliku po „Zaloguj się", z wcięciem następnej linii → znajduje go
    zapytanie w jednej linii i zapytanie złamane inaczej; treść sekcji wraca znak w znak."""
    row = _probe_row("Pojawia się komunikat „Zaloguj się\n   ponownie, aby kontynuować pracę”.")

    await docs.upsert([row])

    one_line = await docs.substring("Zaloguj się ponownie, aby kontynuować pracę")
    rebroken = await docs.substring("Zaloguj się ponownie,\naby  kontynuować")
    read     = await docs.read_by_id([row.section_id])

    assert one_line == [row.section_id]
    assert rebroken == [row.section_id]
    assert read     == [row]


async def test_a_hard_space_in_the_body_matches_a_plain_space(docs: DocsTable) -> None:
    """Twarda spacja w treści → znajduje ją zapytanie ze zwykłą spacją: `\\s` bazy jej nie
    obejmuje, więc wzorzec wymienia ją osobno."""
    row = _probe_row("Opcja „Przekaż\u00a0bufor” wysyła przesyłki do operatora.")

    await docs.upsert([row])

    assert await docs.substring("Przekaż bufor") == [row.section_id]
