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
    """Sprawdza, czy spis treści to jedno zapytanie do tabeli o wszystkie sekcje, bez wyszukiwania
    i bez odczytu po identyfikatorach.

    Wyłapuje narzędzie, które pyta tabelę więcej niż raz albo inną drogą niż spis wszystkich sekcji:
    każde wywołanie spisu kosztowałoby zbędne zapytania do bazy."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    await _tool(client).load()

    assert client.calls == [("list", None)]


async def test_sections_keep_the_order_the_table_gave() -> None:
    """Sprawdza, czy spis zachowuje kolejność, w jakiej sekcje oddała tabela: wiersze podane od
    końca wracają od końca.

    Wyłapuje narzędzie, które samo sortuje sekcje: o kolejności dokumentów i sekcji rozstrzyga
    tabela, więc drugie sortowanie mogłoby ten układ zepsuć."""
    client = ScriptedPostgres(key="section_id", rows=list(reversed(ROWS)))

    result = await _tool(client).load()

    assert result.sections == list(reversed(SECTIONS))


async def test_the_model_gets_descriptions_and_no_content() -> None:
    """Sprawdza, czy tekst dla modelu niesie opisy wszystkich sekcji z identyfikatorami do odczytu,
    ale nie ich treść, choć tabela oddaje wiersze razem z treścią.

    Wyłapuje treść sekcji przeciekającą do spisu: treść ma dawać dopiero odczyt, bo tylko on trafia
    na listę źródeł."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    text = await _tool(client).run(ListDocsArgs())
    body = json.loads(text)

    assert [section["section_id"] for section in body["sections"]] == [
        section.section_id for section in SECTIONS
    ]
    assert "Kto i gdzie nadaje uprawnienie"    in text
    assert "nadaje administrator w Ustawienia" not in text


async def test_the_tool_and_its_fake_tell_the_model_the_same() -> None:
    """Sprawdza, czy narzędzie właściwe i jego atrapa dają modelowi ten sam tekst, gdy stoją na tej
    samej dokumentacji.

    Wyłapuje rozjazd między atrapą a narzędziem: testy grafów na atrapie sprawdzałyby wtedy inny
    tekst niż ten, który model dostanie na produkcji."""
    client = ScriptedPostgres(key="section_id", rows=ROWS)

    real = await _tool(client).run(ListDocsArgs())
    fake = await FakeListDocsTool().run(ListDocsArgs())

    assert real == fake


async def test_an_empty_table_is_an_empty_listing() -> None:
    """Sprawdza, czy pusta tabela dokumentacji daje modelowi pustą listę sekcji, a nie błąd.

    Wyłapuje narzędzie, które przy pustej tabeli zgłasza błąd: dokumentacja, której jeszcze nie
    wgrano, zatrzymywałaby wtedy agenta zamiast dać mu pusty spis."""
    client = ScriptedPostgres(key="section_id")

    body = json.loads(await _tool(client).run(ListDocsArgs()))

    assert body == {"sections": []}


async def test_aclose_closes_the_database_client() -> None:
    """Sprawdza, czy `aclose()` narzędzia zamyka klienta Postgresa, na którym stoi jego tabela.

    Wyłapuje narzędzie, które po sobie nie sprząta: połączenie z bazą zostawałoby otwarte, bo
    sprzątający woła tylko `aclose()` i nie wie, z czego narzędzie jest zbudowane."""
    client = ScriptedPostgres(key="section_id")

    await _tool(client).aclose()

    assert client.closed
