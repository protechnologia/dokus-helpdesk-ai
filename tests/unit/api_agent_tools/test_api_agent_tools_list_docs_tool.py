import json

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.list_docs import FakeListDocsTool, ListDocsArgs, ListDocsTool
from app.db_postgres import DocRow, DocsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `DocsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedzią. Że Postgres układa spis dokument
# po dokumencie, sprawdzają testy na stacku.

SECTIONS = default_sections()
TEXTS    = default_texts()
ROWS     = [
    DocRow.from_section(section, body=TEXTS[section.section_id], ordinal=n).model_dump()
    for n, section in enumerate(SECTIONS)
]


def _tool(
    client: ScriptedPostgres,  # np. ScriptedPostgres(key="section_id", rows=ROWS)
) -> ListDocsTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=ScriptedPostgres(key="section_id", rows=ROWS)

    Example result:
        ListDocsTool odpowiadające bez bazy
    """
    return ListDocsTool(docs=DocsTable(client))


async def test_the_listing_is_one_read_of_the_whole_table() -> None:
    """Spis treści → jedno zapytanie o wszystkie sekcje, bez wyszukiwania i bez odczytu po
    identyfikatorach."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    await _tool(client).load()

    assert client.calls == [("list", None)]


async def test_sections_keep_the_order_the_table_gave() -> None:
    """Tabela oddaje sekcje w swojej kolejności → spis w tej samej: o kolejności dokumentów
    i sekcji rozstrzyga tabela, narzędzie niczego nie sortuje."""
    client = ScriptedPostgres(key="section_id", rows=list(reversed(ROWS)))

    result = await _tool(client).load()

    assert result.sections == list(reversed(SECTIONS))


async def test_the_model_gets_descriptions_and_no_content() -> None:
    """Wiersze z treścią → w tekście dla modelu opisy sekcji pod identyfikatorem do odczytu, bez
    treści: tę daje `read_docs` i tylko on cytuje."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    text = await _tool(client).run(ListDocsArgs())
    body = json.loads(text)

    assert [section["section_id"] for section in body["sections"]] == [
        section.section_id for section in SECTIONS
    ]
    assert "Kto i gdzie nadaje uprawnienie"    in text
    assert "nadaje administrator w Ustawienia" not in text


async def test_the_tool_and_its_fake_tell_the_model_the_same() -> None:
    """Ta sama dokumentacja w tabeli i w atrapie → ten sam tekst dla modelu: test grafu na atrapie
    sprawdza to, co model dostanie na produkcji."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    real = await _tool(client).run(ListDocsArgs())
    fake = await FakeListDocsTool().run(ListDocsArgs())

    assert real == fake


async def test_an_empty_table_is_an_empty_listing() -> None:
    """Tabela bez sekcji → pusty spis, a nie błąd."""
    client = ScriptedPostgres(key="section_id")

    body = json.loads(await _tool(client).run(ListDocsArgs()))

    assert body == {"sections": []}


async def test_aclose_closes_the_database_client() -> None:
    """`aclose()` → zamknięty klient Postgresa: sprzątający nie musi wiedzieć, z czego narzędzie
    jest zbudowane."""
    client = ScriptedPostgres(key="section_id")

    await _tool(client).aclose()

    assert client.closed
