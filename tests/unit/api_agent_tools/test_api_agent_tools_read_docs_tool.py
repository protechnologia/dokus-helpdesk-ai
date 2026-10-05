import pytest

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.read_docs import (
    FakeReadDocsTool,
    ReadDocsQuery,
    ReadDocsTool,
    UnknownSectionError,
)
from app.db_postgres import DocRow, DocsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `DocsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedzią. Że Postgres oddaje treść znak
# w znak i w kolejności żądania, sprawdzają testy na stacku.

SECTIONS = default_sections()
TEXTS    = default_texts()
ROWS     = [
    DocRow.from_section(section, body=TEXTS[section.section_id], ordinal=n).model_dump()
    for n, section in enumerate(SECTIONS)
]

EDORECZENIA, EPUAP, W_TOKU, BRAK_SERWERA = (section.section_id for section in SECTIONS)


def _client() -> ScriptedPostgres:
    """
    Description:
    Klient bez bazy z czterema sekcjami zmyślonej dokumentacji.

    Example args:
        (brak)

    Example result:
        ScriptedPostgres oddający wiersze sekcji po identyfikatorach
    """
    return ScriptedPostgres(key="section_id", rows=ROWS)


def _tool(
    client: ScriptedPostgres,  # np. _client()
) -> ReadDocsTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=_client()

    Example result:
        ReadDocsTool odpowiadające bez bazy
    """
    return ReadDocsTool(docs=DocsTable(client))


async def test_the_read_asks_for_each_section_once() -> None:
    """Sprawdza, czy identyfikator podany dwa razy idzie do tabeli raz: z trzech pozycji z jednym
    powtórzeniem powstaje jedno zapytanie o dwie sekcje, w kolejności żądania, a w wyniku każda
    sekcja jest raz.

    Wyłapuje powtórzenie przeniesione do zapytania albo do wyniku oraz zgubioną kolejność żądania:
    model dostałby tę samą treść dwa razy albo sekcje w innym porządku, niż prosił."""
    client = _client()

    result = await _tool(client).search(ReadDocsQuery(section_ids=[W_TOKU, EDORECZENIA, W_TOKU]))

    assert client.calls == [("read", [W_TOKU, EDORECZENIA])]
    assert [item.section.section_id for item in result.sections] == [W_TOKU, EDORECZENIA]


async def test_a_section_comes_back_with_its_description_and_whole_text() -> None:
    """Sprawdza, czy odczytana sekcja wraca z opisem takim jak zapisany w tabeli i z treścią równą
    zapisanej, znak w znak.

    Wyłapuje narzędzie, które skraca albo zmienia treść: model ma przeczytać sekcję, a nie jej
    skrót."""
    result = await _tool(_client()).search(ReadDocsQuery(section_ids=[BRAK_SERWERA]))

    assert result.sections[0].section == SECTIONS[3]
    assert result.sections[0].text    == TEXTS[BRAK_SERWERA]


async def test_an_unknown_id_fails_the_whole_read() -> None:
    """Sprawdza, czy nieznane identyfikatory wśród znanych kończą cały odczyt wyjątkiem
    `UnknownSectionError`: wyjątek wymienia tylko dwa nieznane, w kolejności żądania, a znanego nie
    ma w komunikacie.

    Wyłapuje wynik częściowy i mylący komunikat: odczyt jednej sekcji zamiast trzech wyglądałby jak
    poprawny, a błąd wymieniający znaną sekcję kazałby agentowi poprawiać nie to, co trzeba."""
    query = ReadDocsQuery(section_ids=["adm-nie-ma", EDORECZENIA, "usr-tez-nie-ma"])

    with pytest.raises(UnknownSectionError) as caught:
        await _tool(_client()).search(query)

    assert caught.value.section_ids == ["adm-nie-ma", "usr-tez-nie-ma"]
    assert EDORECZENIA not in str(caught.value)


async def test_the_tool_and_its_fake_tell_the_model_the_same() -> None:
    """Sprawdza, czy narzędzie właściwe i jego atrapa dają dla tej samej dokumentacji ten sam tekst
    dla modelu i te same źródła.

    Wyłapuje rozjazd między atrapą a narzędziem: testy grafów na atrapie sprawdzałyby wtedy coś
    innego niż to, co model dostanie na produkcji."""
    query = ReadDocsQuery(section_ids=[W_TOKU, EDORECZENIA])
    real  = _tool(_client())
    fake  = FakeReadDocsTool()

    real_result = await real.search(query)
    fake_result = await fake.search(query)

    assert real.render_for_model(real_result) == fake.render_for_model(fake_result)
    assert real.cite(real_result)             == fake.cite(fake_result)


async def test_only_sections_that_were_read_are_cited() -> None:
    """Sprawdza, czy dwie odczytane sekcje dają dokładnie dwa źródła z materiału „docs”,
    w kolejności odczytu, a tytuł źródła składa się z nazwy dokumentu, wersji i tytułu sekcji.

    Wyłapuje listę źródeł niezgodną z odczytanymi sekcjami albo tytuł bez wydania dokumentu:
    człowiek nie wiedziałby, do której wersji instrukcji odpowiedź się odwołuje."""
    tool   = _tool(_client())
    result = await tool.search(ReadDocsQuery(section_ids=[W_TOKU, EDORECZENIA]))

    refs = tool.cite(result)

    assert [ref.key for ref in refs] == [f"docs:{W_TOKU}", f"docs:{EDORECZENIA}"]
    assert refs[0].title == "Instrukcja użytkownika 4.12 — Status „W toku” przy wysyłce ePUAP"


async def test_aclose_closes_the_database_client() -> None:
    """Sprawdza, czy `aclose()` narzędzia zamyka klienta Postgresa, na którym stoi jego tabela.

    Wyłapuje narzędzie, które po sobie nie sprząta: połączenie z bazą zostawałoby otwarte, bo
    sprzątający woła tylko `aclose()` i nie wie, z czego narzędzie jest zbudowane."""
    client = _client()

    await _tool(client).aclose()

    assert client.closed
