import json

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.find_docs_text import FindDocsTextQuery, FindDocsTextTool
from app.db_postgres import DocRow, DocsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `DocsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedziami. Że Postgres naprawdę tak
# dopasowuje, sprawdzają testy na stacku.

SECTIONS = default_sections()
TEXTS    = default_texts()
ROWS     = [
    DocRow.from_section(section, body=TEXTS[section.section_id], ordinal=n).model_dump()
    for n, section in enumerate(SECTIONS)
]

EDORECZENIA, EPUAP, W_TOKU, BRAK_SERWERA = (section.section_id for section in SECTIONS)


def _client(
    substring: dict[str, list[str]] | None = None,  # np. {"PDP-203": ["adm-kancelaria-epuap"]}
    words:     dict[str, list[str]] | None = None,  # np. {"uprawnienie": ["adm-…", "adm-…"]}
) -> ScriptedPostgres:
    """
    Description:
    Klient bez bazy ze zmyśloną dokumentacją: na frazę i na słowa oddaje ustalone identyfikatory.

    Example args:
        substring={"PDP-203": ["adm-kancelaria-epuap"]}
        words={"uprawnienie": ["adm-kancelaria-edoreczenia"]}

    Example result:
        ScriptedPostgres odpowiadający jedną sekcją na frazę „PDP-203"
    """
    return ScriptedPostgres(key="section_id", rows=ROWS, substring=substring, words=words)


def _tool(
    client: ScriptedPostgres,  # np. _client(words={"uprawnienie": [EDORECZENIA]})
    limit:  int = 5,           # np. 5 — RAG_TOP_K
) -> FindDocsTextTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=_client(words={"uprawnienie": ["adm-kancelaria-edoreczenia"]})

    Example result:
        FindDocsTextTool odpowiadające bez bazy
    """
    return FindDocsTextTool(docs=DocsTable(client), limit=limit)


async def test_the_phrase_goes_by_substring_and_the_words_by_dictionary() -> None:
    """Sprawdza, czy narzędzie pyta tabelę dwiema drogami, każdą raz: frazę „Przekaż bufor” wysyła
    do szukania podciągu, a słowa „sekwencja numeracja” do szukania przez słownik.

    Wyłapuje pomylenie dróg albo wartości: fraza ma być szukana dosłownie, a słowa w dowolnej
    odmianie, więc po zamianie narzędzie bez żadnego błędu znajdowałoby inne sekcje."""
    client = _client()

    await _tool(client).find(FindDocsTextQuery(exact="Przekaż bufor", words="sekwencja numeracja"))

    assert client.calls == [
        ("substring", "Przekaż bufor"),
        ("words",     "sekwencja numeracja"),
    ]


async def test_a_field_that_was_not_given_is_not_searched() -> None:
    """Sprawdza, czy narzędzie pyta tabelę tylko o to, co agent podał: przy samej frazie nie ma
    zapytania przez słownik, a przy samych słowach nie ma szukania podciągu.

    Wyłapuje narzędzie, które szuka także tą drogą, której agent nie użył: do bazy szłoby zbędne
    zapytanie z pustą wartością."""
    only_exact = _client()
    only_words = _client()

    await _tool(only_exact).find(FindDocsTextQuery(exact="PDP-203"))
    await _tool(only_words).find(FindDocsTextQuery(words="uprawnienie"))

    assert [kind for kind, _ in only_exact.calls] == ["substring"]
    assert [kind for kind, _ in only_words.calls] == ["words"]


async def test_either_field_is_enough_for_a_section_to_come_back() -> None:
    """Sprawdza, czy wyniki obu dróg się sumują: fraza „PDP-203” trafia w jedną sekcję, słowo
    „numeracja” w inną, a w wyniku są obie, znaleziona frazą pierwsza, i nic nie jest pominięte.

    Wyłapuje narzędzie, które wymaga dopasowania obiema drogami naraz albo miesza kolejność: sekcja
    pasująca tylko do frazy albo tylko do słów zniknęłaby z wyniku."""
    client = _client(substring={"PDP-203": [BRAK_SERWERA]}, words={"numeracja": [W_TOKU]})

    result = await _tool(client).find(FindDocsTextQuery(exact="PDP-203", words="numeracja"))

    assert [(found.section.section_id, found.matched_by) for found in result.sections] == [
        (BRAK_SERWERA, "exact"),
        (W_TOKU,       "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_section_found_both_ways_comes_back_once_as_exact() -> None:
    """Sprawdza, czy sekcja znaleziona i frazą, i słowami jest w wyniku raz, z etykietą `exact`,
    a druga sekcja, znaleziona tylko słowami, stoi za nią z etykietą `words`.

    Wyłapuje sekcję powtórzoną w wyniku albo oznaczoną jako znaleziona słowami: model dostałby dwa
    wpisy o tym samym albo nie wiedziałby, że trafiła w nią dosłowna fraza."""
    client = _client(substring={"PDP-203": [EPUAP]}, words={"skrzynka": [EPUAP, W_TOKU]})

    result = await _tool(client).find(FindDocsTextQuery(exact="PDP-203", words="skrzynka"))

    assert [(found.section.section_id, found.matched_by) for found in result.sections] == [
        (EPUAP,  "exact"),
        (W_TOKU, "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_matches_over_the_limit_are_counted_and_not_read() -> None:
    """Sprawdza, czy limit przycina wynik i liczy resztę: przy czterech pasujących sekcjach
    i limicie 2 wracają dwie pierwsze, dwie są policzone jako pominięte, a z tabeli czytane są opisy
    tylko tych dwóch.

    Wyłapuje trzy usterki: wynik dłuższy niż limit, zgubiony licznik pominiętych (agent nie
    wiedziałby, że zapytanie było zbyt ogólne) i czytanie z bazy sekcji, które i tak odpadają."""
    client = _client(words={"uprawnienie": [EDORECZENIA, EPUAP, W_TOKU, BRAK_SERWERA]})

    result = await _tool(client, limit=2).find(FindDocsTextQuery(words="uprawnienie"))

    assert [found.section.section_id for found in result.sections] == [EDORECZENIA, EPUAP]
    assert result.omitted_over_limit == 2
    assert client.calls[-1]          == ("read", [EDORECZENIA, EPUAP])


async def test_the_model_gets_descriptions_and_no_content() -> None:
    """Sprawdza, czy znaleziona sekcja wraca jako sam opis: w tekście dla modelu jest jej
    identyfikator do odczytu, a nie ma treści sekcji, choć tabela oddaje ją razem z wierszem.

    Wyłapuje treść sekcji przeciekającą do wyniku wyszukiwania: model mógłby oprzeć na niej
    odpowiedź bez odczytu, a tylko odczyt trafia na listę źródeł."""
    client = _client(substring={"Nie udało się": [BRAK_SERWERA]})
    tool   = _tool(client)

    result = await tool.find(FindDocsTextQuery(exact="Nie udało się"))
    text   = await tool.run(FindDocsTextQuery(exact="Nie udało się"))

    assert result.sections[0].section == SECTIONS[3]
    assert json.loads(text)["sections"][0]["section"]["section_id"] == BRAK_SERWERA
    assert "limity zasobów" not in text


async def test_nothing_found_is_an_empty_result_and_no_read() -> None:
    """Sprawdza, czy brak trafień daje pusty wynik: żadnych sekcji, zero pominiętych i żadnego
    odczytu z tabeli.

    Wyłapuje narzędzie, które przy braku trafień zgłasza błąd albo mimo to czyta z bazy: odpowiedź,
    że dokumentacja o tym milczy, jest poprawna i nie wymaga kolejnego zapytania."""
    client = _client()

    result = await _tool(client).find(FindDocsTextQuery(exact="KSeF", words="faktura"))

    assert result.sections           == []
    assert result.omitted_over_limit == 0
    assert "read" not in [kind for kind, _ in client.calls]


async def test_aclose_closes_the_database_client() -> None:
    """Sprawdza, czy `aclose()` narzędzia zamyka klienta Postgresa, na którym stoi jego tabela.

    Wyłapuje narzędzie, które po sobie nie sprząta: połączenie z bazą zostawałoby otwarte, bo
    sprzątający woła tylko `aclose()` i nie wie, z czego narzędzie jest zbudowane."""
    client = _client()

    await _tool(client).aclose()

    assert client.closed
