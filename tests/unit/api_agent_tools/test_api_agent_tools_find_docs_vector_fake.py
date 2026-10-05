import json

from app.agent_tools.docs.find_docs_vector import FakeFindDocsVectorTool, FindDocsVectorQuery

QUERY = FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

FOUND_IDS = ["adm-kancelaria-edoreczenia", "adm-kancelaria-epuap"]


async def test_the_result_is_the_same_on_every_search() -> None:
    """Sprawdza, czy atrapa wyszukiwania po znaczeniu w dokumentacji oddaje za każdym razem ten sam
    wynik: dwa wyszukiwania dają te same dwie sekcje w tej samej kolejności.

    Wyłapuje atrapę, której wynik zmienia się między wywołaniami: testy grafów, które odwołują się
    do jej stałych identyfikatorów, przestałyby być powtarzalne."""
    tool = FakeFindDocsVectorTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [found.section.section_id for found in first.sections]  == FOUND_IDS
    assert [found.section.section_id for found in second.sections] == FOUND_IDS


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje każde zapytanie w publicznej liście `queries`: po jednym
    wyszukaniu jest tam dokładnie to zapytanie.

    Wyłapuje atrapę, która gubi zapytania: test grafu nie mógłby wtedy sprawdzić, o co agent
    pytał."""
    tool = FakeFindDocsVectorTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_section_descriptions_it_can_read_by_id() -> None:
    """Sprawdza, czy tekst dla modelu jest JSON-em, w którym każda sekcja ma identyfikator, wydanie
    dokumentu i podobieństwo (`score`), a nie ma żadnego innego pola ani treści sekcji.

    Wyłapuje dwie usterki: wynik bez identyfikatora, którym agent prosi potem o odczyt, oraz treść
    sekcji w wyniku wyszukiwania, która pozwoliłaby modelowi pominąć odczyt, a z nim źródło."""
    tool = FakeFindDocsVectorTool()
    text = await tool.run(QUERY)
    body = json.loads(text)

    assert [found["section"]["section_id"] for found in body["sections"]] == FOUND_IDS
    assert [found["score"] for found in body["sections"]]                 == [0.74, 0.68]
    assert body["sections"][0]["section"]["version"]                      == "4.12"
    assert set(body["sections"][0]) == {"score", "section"}
    assert "nadaje administrator" not in text


async def test_a_cut_threshold_is_told_apart_from_no_hits() -> None:
    """Sprawdza, czy liczba sekcji odciętych progiem trafia do tekstu dla modelu: atrapa bez sekcji
    i z licznikiem 3 oddaje pustą listę oraz `dropped_below_threshold` równe 3.

    Wyłapuje wynik, który gubi ten licznik: dla agenta „niczego nie było” i „próg wszystko wyciął”
    to różne sytuacje, a wyglądałyby tak samo."""
    tool = FakeFindDocsVectorTool(found=[], dropped_below_threshold=3)
    body = json.loads(await tool.run(QUERY))

    assert body == {"sections": [], "dropped_below_threshold": 3}


def test_the_search_cannot_be_cited() -> None:
    """Sprawdza, czy atrapa wyszukiwania po znaczeniu w dokumentacji nie ma metody `cite()`.

    Wyłapuje wyszukiwanie, które zaczęło cytować: na listę źródeł trafiłby opis znalezionej sekcji,
    choć model jej treści nie przeczytał."""
    assert not hasattr(FakeFindDocsVectorTool(), "cite")
