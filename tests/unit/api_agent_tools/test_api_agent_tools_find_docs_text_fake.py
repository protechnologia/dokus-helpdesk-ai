import json

from app.agent_tools.docs.find_docs_text import FakeFindDocsTextTool, FindDocsTextQuery

QUERY = FindDocsTextQuery(exact="Nie udało się skomunikować z serwerem")

FOUND_IDS = ["usr-komunikat-brak-serwera", "adm-kancelaria-edoreczenia"]


async def test_the_result_is_the_same_on_every_search() -> None:
    """Sprawdza, czy atrapa wyszukiwania tekstowego w dokumentacji oddaje za każdym razem ten sam
    wynik: dwa wyszukiwania dają te same dwie sekcje w tej samej kolejności, z sekcją znalezioną po
    dosłownej frazie na pierwszym miejscu.

    Wyłapuje atrapę, której wynik zmienia się między wywołaniami: testy grafów, które odwołują się
    do jej stałych identyfikatorów, przestałyby być powtarzalne."""
    tool = FakeFindDocsTextTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [matched.section.section_id for matched in first.sections]  == FOUND_IDS
    assert [matched.section.section_id for matched in second.sections] == FOUND_IDS


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje każde zapytanie w publicznej liście `queries`: po jednym
    wyszukaniu jest tam dokładnie to zapytanie.

    Wyłapuje atrapę, która gubi zapytania: test grafu nie mógłby wtedy sprawdzić, o co agent
    pytał."""
    tool = FakeFindDocsTextTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_how_each_section_was_found() -> None:
    """Sprawdza, czy tekst dla modelu jest JSON-em, w którym każda sekcja ma identyfikator i pole
    `matched_by` mówiące, czym ją znaleziono: `exact` (frazą) albo `words` (słowami).

    Wyłapuje wynik bez informacji o sposobie dopasowania albo z inną nazwą niż pole, którym agent
    pytał: model nie wiedziałby, która część jego zapytania trafiła."""
    tool = FakeFindDocsTextTool()
    body = json.loads(await tool.run(QUERY))

    assert [found["section"]["section_id"] for found in body["sections"]] == FOUND_IDS
    assert [found["matched_by"] for found in body["sections"]]            == ["exact", "words"]


async def test_the_model_gets_no_piece_of_the_content() -> None:
    """Sprawdza, czy wynik wyszukiwania niesie przy sekcji tylko sposób dopasowania i jej opis: nie
    ma żadnego innego pola, a w tekście dla modelu nie pada zdanie z treści sekcji.

    Wyłapuje fragment treści dołożony do wyniku wyszukiwania: mógłby modelowi wystarczyć zamiast
    odczytu sekcji, a wtedy odpowiedź niosłaby treść, której nie ma na liście źródeł."""
    tool = FakeFindDocsTextTool()
    text = await tool.run(QUERY)
    body = json.loads(text)

    assert set(body["sections"][0]) == {"matched_by", "section"}
    assert "nadaje administrator" not in text


async def test_matches_over_the_limit_are_counted() -> None:
    """Sprawdza, czy liczba sekcji pominiętych ponad limit trafia do tekstu dla modelu: atrapa bez
    sekcji i z licznikiem 12 oddaje pustą listę oraz `omitted_over_limit` równe 12.

    Wyłapuje wynik, który gubi ten licznik: agent nie dowiedziałby się, że zapytanie było za ogólne
    i że pasujących sekcji jest więcej, niż zobaczył."""
    tool = FakeFindDocsTextTool(matched=[], omitted_over_limit=12)
    body = json.loads(await tool.run(QUERY))

    assert body == {"sections": [], "omitted_over_limit": 12}


def test_the_search_cannot_be_cited() -> None:
    """Sprawdza, czy atrapa wyszukiwania tekstowego w dokumentacji nie ma metody `cite()`.

    Wyłapuje wyszukiwanie, które zaczęło cytować: na listę źródeł trafiłby opis znalezionej sekcji,
    choć model jej treści nie przeczytał."""
    assert not hasattr(FakeFindDocsTextTool(), "cite")
