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
    """Zapytanie agenta → jego tekst bez zmian, w trybie query: w kolekcji leżą wektory passage,
    a pomyłka trybu nie pada, tylko daje trochę gorsze wyniki."""
    seen: list = []

    await _tool([], embedder_seen=seen).find(QUERY)

    assert seen[0]["body"] == {"texts": [QUERY.text], "mode": "query"}


async def test_the_search_asks_for_top_k_sections_in_the_section_space() -> None:
    """Wyszukanie → wektor z embeddera, przestrzeń `section`, grupy po sekcji i limit
    z konfiguracji: limit liczy sekcje, a liczby wyników nie ustala agent."""
    seen: list = []

    await _tool([], top_k=7, qdrant_seen=seen).find(QUERY)

    assert seen[0]["body"]["query"]    == QUERY_VECTOR
    assert seen[0]["body"]["using"]    == VECTOR_SECTION
    assert seen[0]["body"]["group_by"] == "section_id"
    assert seen[0]["body"]["limit"]    == 7


async def test_sections_below_the_threshold_are_dropped_and_counted() -> None:
    """Cztery sekcje, próg 0.37 → dwie zwrócone i dwie policzone jako odcięte: „próg to wyciął"
    i „dokumentacja o tym milczy" to różne odpowiedzi."""
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
    """Trafienie → opis sekcji odtworzony z payloadu i podobieństwo zaokrąglone do trzech miejsc;
    w tekście dla modelu identyfikator stoi tam, gdzie poda go `read_docs`."""
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
    """Qdrant nic nie zwrócił → pusty wynik bez odciętych: pusta kolekcja to nie awaria."""
    result = await _tool([]).find(QUERY)

    assert result.sections                == []
    assert result.dropped_below_threshold == 0


async def test_a_payload_that_is_not_a_section_is_a_config_error_naming_the_fields() -> None:
    """Payload bez tytułu sekcji → `DbQdrantConfigError` z identyfikatorem punktu, nazwą pola
    i komendą przebudowy: indeks zbudowany inną wersją kontraktu naprawia przebudowa, nie
    czekanie."""
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
    """Zepsuty payload poniżej progu → brak błędu: odcięte trafienie nie trafia do wyniku, więc
    nie ma czego sprawdzać."""
    result = await _tool([_hit(SECTIONS[0], 0.20, payload={})]).find(QUERY)

    assert result.sections                == []
    assert result.dropped_below_threshold == 1


async def test_aclose_closes_both_clients() -> None:
    """`aclose()` → zamknięte połączenia embeddera i Qdranta: sprzątający nie musi wiedzieć,
    z czego narzędzie jest zbudowane."""
    tool = _tool([])

    await tool.aclose()

    assert tool._embedder._client.is_closed
    assert tool._docs._client._client.is_closed
