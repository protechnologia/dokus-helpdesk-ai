import json

import httpx
import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery, FindDocsVectorTool
from app.core_model.docs.doc_section import DocSection
from app.db_qdrant import VECTOR_SECTION, DbQdrantConfigError, DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests.helpers_transport import capturing, with_transport

# Narzędzie stoi na prawdziwych klientach embeddera i Qdranta, a podmieniony jest tylko transport
# — sprawdzamy więc to, co faktycznie idzie na drut (tryb, przestrzeń wektorów, grupowanie, limit).

QUERY = FindDocsVectorQuery(text="kto nadaje uprawnienie do kancelarii e-Doręczeń")

QUERY_VECTOR = [0.1, 0.2, 0.3, 0.4]

SECTIONS = default_sections()


def _hit(
    section: DocSection,          # np. SECTIONS[0]
    score:   float,               # np. 0.58
    payload: dict | None = None,  # np. {"section_id": "adm-…"} — gdy test psuje payload
) -> dict:
    """
    Description:
    Jedna grupa w kształcie, w jakim oddaje ją Qdrant: sekcja i jej najbliższy fragment
    z opisem sekcji w payloadzie, takim, jaki zapisuje indeksacja.

    Example args:
        section=DocSection(section_id="adm-kancelaria-edoreczenia", …)
        score=0.58

    Example result:
        {"id": "adm-kancelaria-edoreczenia", "hits": [{"id": "p-adm-…", "score": 0.58, …}]}
    """
    hit = {
        "id":      f"p-{section.section_id}",
        "score":   score,
        "payload": payload if payload is not None else section.model_dump(mode="json"),
    }

    return {"id": section.section_id, "hits": [hit]}


def _tool(
    groups:        list[dict],          # np. [_hit(SECTIONS[0], 0.58)]
    score_min:     float       = 0.37,  # np. 0.37 — RAG_DOCS_SCORE_MIN
    top_k:         int         = 5,     # np. 5 — RAG_TOP_K
    embedder_seen: list | None = None,  # żądania do embeddera, gdy test je sprawdza
    qdrant_seen:   list | None = None,  # żądania do Qdranta, gdy test je sprawdza
) -> FindDocsVectorTool:
    """
    Description:
    Buduje narzędzie na prawdziwych klientach z podmienionym transportem: embedder oddaje jeden
    stały wektor, Qdrant podane grupy.

    Example args:
        groups=[_hit(SECTIONS[0], 0.58)]

    Example result:
        FindDocsVectorTool odpowiadające jedną sekcją, bez żadnej usługi
    """
    embedder = with_transport(
        EmbeddingClient(base_url="http://embedder:8000"),
        capturing(
            embedder_seen if embedder_seen is not None else [],
            {("POST", "/embed"): httpx.Response(200, json={"vectors": [QUERY_VECTOR]})},
        ),
    )
    qdrant = with_transport(
        QdrantClient(base_url="http://qdrant:6333"),
        capturing(
            qdrant_seen if qdrant_seen is not None else [],
            {
                ("POST", "/collections/docs/points/query/groups"):
                    httpx.Response(200, json={"result": {"groups": groups}}),
            },
        ),
    )

    tool = FindDocsVectorTool(
        embedder  = embedder,
        docs      = DocsCollection(qdrant, "docs", len(QUERY_VECTOR)),
        top_k     = top_k,
        score_min = score_min,
    )

    return tool


async def test_the_query_is_embedded_in_query_mode_as_it_was_asked() -> None:
    """Sprawdza, czy do embeddera idzie tekst zapytania agenta bez zmian i w trybie `query`.

    Wyłapuje zmieniony tekst albo pomylony tryb: w kolekcji leżą wektory liczone w trybie `passage`,
    a pomyłka trybu nie kończy się błędem, tylko trochę gorszymi wynikami."""
    seen: list = []

    await _tool([], embedder_seen=seen).find(QUERY)

    assert seen[0]["body"] == {"texts": [QUERY.text], "mode": "query"}


async def test_the_search_asks_for_top_k_sections_in_the_section_space() -> None:
    """Sprawdza, czy do Qdranta idzie właściwe zapytanie: wektor zapytania z embeddera, nazwa
    wektora `section`, grupowanie po `section_id` i limit z konfiguracji (tu 7).

    Wyłapuje zapytanie po niewłaściwym wektorze, bez grupowania albo z innym limitem: limit ma
    liczyć sekcje, nie ich fragmenty, a liczby wyników nie ustala agent."""
    seen: list = []

    await _tool([], top_k=7, qdrant_seen=seen).find(QUERY)

    assert seen[0]["body"]["query"]    == QUERY_VECTOR
    assert seen[0]["body"]["using"]    == VECTOR_SECTION
    assert seen[0]["body"]["group_by"] == "section_id"
    assert seen[0]["body"]["limit"]    == 7


async def test_sections_below_the_threshold_are_dropped_and_counted() -> None:
    """Sprawdza, czy próg podobieństwa dzieli trafienia: z czterech sekcji o podobieństwie 0.58,
    0.37, 0.36 i 0.31 przy progu 0.37 wracają dwie pierwsze, a dwie są policzone jako odcięte.

    Wyłapuje próg, który odcina sekcję stojącą dokładnie na nim albo przepuszcza słabsze, oraz
    zgubiony licznik: bez niego „próg to wyciął” wygląda jak „dokumentacja o tym milczy”."""
    groups = [
        _hit(SECTIONS[0], 0.58),
        _hit(SECTIONS[1], 0.37),
        _hit(SECTIONS[2], 0.36),
        _hit(SECTIONS[3], 0.31),
    ]

    result = await _tool(groups, score_min=0.37).find(QUERY)

    assert [found.section.section_id for found in result.sections] == [
        SECTIONS[0].section_id,
        SECTIONS[1].section_id,
    ]
    assert result.dropped_below_threshold == 2


async def test_a_section_comes_back_as_its_description_and_a_rounded_score() -> None:
    """Sprawdza, czy trafienie z Qdranta wraca jako opis sekcji odtworzony z payloadu,
    z podobieństwem zaokrąglonym do trzech miejsc (0.58123456 daje 0.581), i czy tekst dla modelu to
    ten sam wynik zapisany jako JSON.

    Wyłapuje opis sekcji zmieniony po drodze z indeksu albo inny kształt JSON-u: model nie znalazłby
    identyfikatora w polu, z którego bierze go do odczytu sekcji."""
    tool = _tool([_hit(SECTIONS[0], 0.58123456)])

    result = await tool.find(QUERY)
    text   = await tool.run(QUERY)

    assert result.sections[0].section == SECTIONS[0]
    assert result.sections[0].score   == 0.581
    assert json.loads(text) == {
        "sections": [{"score": 0.581, "section": SECTIONS[0].model_dump(mode="json")}],
        "dropped_below_threshold": 0,
    }


async def test_no_hits_is_an_empty_result_not_an_error() -> None:
    """Sprawdza, czy pusta odpowiedź Qdranta daje pusty wynik: żadnych sekcji i zero odciętych.

    Wyłapuje narzędzie, które przy braku trafień zgłasza błąd: pusta kolekcja to nie awaria, tylko
    odpowiedź, że niczego nie znaleziono."""
    result = await _tool([]).find(QUERY)

    assert result.sections                == []
    assert result.dropped_below_threshold == 0


async def test_a_payload_that_is_not_a_section_is_a_config_error_naming_the_fields() -> None:
    """Sprawdza, czy trafienie, którego payload nie ma tytułu sekcji, kończy się wyjątkiem
    `DbQdrantConfigError`, a komunikat podaje identyfikator punktu, nazwę brakującego pola i komendę
    przebudowy indeksu, ale nie cytuje zawartości payloadu.

    Wyłapuje błąd, z którego nie wynika, co jest zepsute i jak to naprawić: indeks zbudowany inną
    wersją kontraktu naprawia przebudowa, a nie czekanie."""
    broken = SECTIONS[0].model_dump(mode="json")
    del broken["title"]

    with pytest.raises(DbQdrantConfigError) as raised:
        await _tool([_hit(SECTIONS[0], 0.58, payload=broken)]).find(QUERY)

    message = str(raised.value)

    assert f"p-{SECTIONS[0].section_id}" in message
    assert "title"                       in message
    assert "docs index"                  in message
    assert broken["description"]     not in message


async def test_a_dropped_hit_is_never_looked_at() -> None:
    """Sprawdza, czy trafienie poniżej progu nie jest w ogóle sprawdzane: zepsuty payload przy
    podobieństwie 0.20 nie daje błędu, tylko pusty wynik z jednym odciętym trafieniem.

    Wyłapuje sprawdzanie payloadu przed odcięciem progiem: zepsuty punkt, który i tak nie trafiłby
    do wyniku, zatrzymywałby całe wyszukiwanie."""
    result = await _tool([_hit(SECTIONS[0], 0.20, payload={})]).find(QUERY)

    assert result.sections                == []
    assert result.dropped_below_threshold == 1


async def test_aclose_closes_both_clients() -> None:
    """Sprawdza, czy `aclose()` narzędzia zamyka oba połączenia: z embedderem i z Qdrantem.

    Wyłapuje narzędzie, które zamyka tylko jedno z nich albo żadnego: połączenia zostawałyby
    otwarte, bo sprzątający woła tylko `aclose()` i nie wie, z czego narzędzie jest zbudowane."""
    tool = _tool([])

    await tool.aclose()

    assert tool._embedder._client.is_closed
    assert tool._docs._client._client.is_closed
