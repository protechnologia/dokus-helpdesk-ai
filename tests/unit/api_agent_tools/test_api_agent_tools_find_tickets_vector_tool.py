import json

import httpx
import pytest

from app.agent_tools.tickets.find_tickets_vector import (
    FindTicketsVectorQuery,
    FindTicketsVectorTool,
)
from app.core_model.ticket_parsed import ParsedTicket
from app.db_qdrant import VECTOR_PROBLEM, DbQdrantConfigError, QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests.helpers_transport import capturing, with_transport

# Narzędzie stoi na prawdziwych klientach embeddera i Qdranta, a podmieniony jest tylko transport
# — sprawdzamy więc to, co faktycznie idzie na drut (tryb, przestrzeń wektorów, limit).

QUERY = FindTicketsVectorQuery(
    problem  = "Nie przychodzą przesyłki z e-Doręczeń",
    symptoms = "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
)

QUERY_VECTOR = [0.1, 0.2, 0.3, 0.4]


def _payload(
    ticket_id: str,  # np. "90001"
) -> dict:
    """
    Description:
    Payload punktu, jaki zapisuje indeksacja — wszystkie pola `ParsedTicket`, treść zmyślona.

    Example args:
        ticket_id="90001"

    Example result:
        {"ticket_id": "90001", "date": "2026-02-10", "component": "e-Doręczenia", …}
    """
    payload = {
        "ticket_id":                     ticket_id,
        "date":                          "2026-02-10",
        "component":                     "e-Doręczenia",
        "problem":                       "Nie przychodzą przesyłki z e-Doręczeń",
        "symptoms":                      "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę",
        "error_codes":                   [],
        "cause":                         "Zacięta kolejka pobierania po przerwanym połączeniu",
        "solution":                      "Zrestartowano kolejkę; zaległe przesyłki pobrały się.",
        "resolution":                    "naprawione",
        "questions_summary":             "pytano, od kiedy brak przesyłek",
        "resolution_vocabulary_version": 1,
    }

    return payload


def _hit(
    ticket_id: str,               # np. "90001"
    score:     float,             # np. 0.71
    payload:   dict | None = None,  # np. {"ticket_id": "90001"} — gdy test psuje payload
) -> dict:
    """
    Description:
    Jedno trafienie w kształcie, w jakim oddaje je Qdrant.

    Example args:
        ticket_id="90001"
        score=0.71

    Example result:
        {"id": "p-90001", "score": 0.71, "payload": {"ticket_id": "90001", …}}
    """
    hit = {
        "id":      f"p-{ticket_id}",
        "score":   score,
        "payload": payload if payload is not None else _payload(ticket_id),
    }

    return hit


def _tool(
    hits:          list[dict],           # np. [_hit("90001", 0.71)]
    score_min:     float       = 0.48,   # np. 0.48 — RAG_SCORE_MIN
    top_k:         int         = 5,      # np. 5 — RAG_TOP_K
    embedder_seen: list | None = None,   # żądania do embeddera, gdy test je sprawdza
    qdrant_seen:   list | None = None,   # żądania do Qdranta, gdy test je sprawdza
) -> FindTicketsVectorTool:
    """
    Description:
    Buduje narzędzie na prawdziwych klientach z podmienionym transportem: embedder oddaje jeden
    stały wektor, Qdrant podane trafienia.

    Example args:
        hits=[_hit("90001", 0.71)]

    Example result:
        FindTicketsVectorTool odpowiadające jednym trafieniem, bez żadnej usługi
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
                ("POST", "/collections/tickets/points/query"):
                    httpx.Response(200, json={"result": {"points": hits}}),
            },
        ),
    )

    tool = FindTicketsVectorTool(
        embedder  = embedder,
        tickets   = TicketsCollection(qdrant, "tickets", len(QUERY_VECTOR)),
        top_k     = top_k,
        score_min = score_min,
    )

    return tool


async def test_the_query_is_embedded_in_query_mode_from_problem_and_symptoms() -> None:
    """Zapytanie agenta → jeden tekst `problem` + `symptoms` w trybie query: ten sam tekst, który
    dla rekordu o tych polach składa indeksacja, inaczej wektory nie byłyby porównywalne."""
    seen: list = []

    await _tool([], embedder_seen=seen).find(QUERY)

    indexed = ParsedTicket(**{**_payload("90001"), **QUERY.model_dump()})

    assert seen[0]["body"] == {"texts": [f"{QUERY.problem}\n{QUERY.symptoms}"], "mode": "query"}
    assert seen[0]["body"]["texts"] == [indexed.embedding_text()]


async def test_the_search_goes_to_the_problem_vectors_with_top_k() -> None:
    """Wyszukanie → wektor z embeddera, przestrzeń `problem`, limit z konfiguracji: wektor query
    wolno porównywać wyłącznie z wektorami `problem`, a liczby trafień nie ustala agent."""
    seen: list = []

    await _tool([], top_k=7, qdrant_seen=seen).find(QUERY)

    assert seen[0]["body"]["query"] == QUERY_VECTOR
    assert seen[0]["body"]["using"] == VECTOR_PROBLEM
    assert seen[0]["body"]["limit"] == 7


async def test_hits_below_the_threshold_are_dropped_and_counted() -> None:
    """Pięć trafień, próg 0.48 → dwa zwrócone i trzy policzone jako odcięte: „próg to wyciął"
    i „nic nie było" to różne odpowiedzi."""
    hits = [
        _hit("90001", 0.71),
        _hit("90003", 0.52),
        _hit("90004", 0.47),
        _hit("90005", 0.41),
        _hit("90006", 0.33),
    ]

    result = await _tool(hits, score_min=0.48).find(QUERY)

    assert [found.ticket_id for found in result.tickets] == ["90001", "90003"]
    assert [found.score for found in result.tickets]     == [0.71, 0.52]
    assert result.dropped_below_threshold == 3


async def test_a_hit_comes_back_as_its_number_and_a_rounded_score() -> None:
    """Trafienie → numer zgłoszenia z payloadu i podobieństwo zaokrąglone do trzech miejsc: dalsze
    cyfry to szum, a treść karty model ma odczytać osobnym narzędziem."""
    tool = _tool([_hit("90001", 0.71234567)])

    result = await tool.find(QUERY)
    text   = await tool.run(QUERY)

    assert result.tickets[0].model_dump() == {"ticket_id": "90001", "score": 0.712}
    assert json.loads(text) == {
        "tickets":                 [{"ticket_id": "90001", "score": 0.712}],
        "dropped_below_threshold": 0,
    }
    assert "kolejkę" not in text


async def test_no_hits_is_an_empty_result_not_an_error() -> None:
    """Qdrant nic nie zwrócił → pusty wynik bez odciętych: „nowy typ problemu" to poprawna
    odpowiedź dla blisko połowy korpusu."""
    result = await _tool([]).find(QUERY)

    assert result.tickets == []
    assert result.dropped_below_threshold == 0


async def test_a_hit_without_a_ticket_number_is_a_config_error_without_content() -> None:
    """Payload bez numeru zgłoszenia → `DbQdrantConfigError` z identyfikatorem punktu, ale bez
    treści: indeks zbudowany inaczej naprawia przebudowa, a treść zgłoszenia nie trafia do logów."""
    broken = _payload("90001")
    del broken["ticket_id"]

    with pytest.raises(DbQdrantConfigError) as raised:
        await _tool([_hit("90001", 0.71, payload=broken)]).find(QUERY)

    message = str(raised.value)

    assert "p-90001" in message
    assert "rag reindex" in message
    assert broken["problem"] not in message


async def test_the_search_does_not_check_the_rest_of_the_payload() -> None:
    """Payload z samym numerem zgłoszenia → poprawne trafienie: wyszukiwanie oddaje numery,
    a kontrakt karty sprawdza dopiero odczyt (`read_tickets_card`)."""
    result = await _tool([_hit("90001", 0.71, payload={"ticket_id": "90001"})]).find(QUERY)

    assert [found.ticket_id for found in result.tickets] == ["90001"]


async def test_a_dropped_hit_is_never_looked_at() -> None:
    """Trafienie bez numeru poniżej progu → brak błędu: odcięte trafienie nie trafia do wyniku,
    więc nie ma czego sprawdzać."""
    result = await _tool([_hit("90001", 0.20, payload={})]).find(QUERY)

    assert result.tickets == []
    assert result.dropped_below_threshold == 1


async def test_aclose_closes_both_clients() -> None:
    """`aclose()` → zamknięte połączenia embeddera i Qdranta: sprzątający nie musi wiedzieć,
    z czego narzędzie jest zbudowane."""
    tool = _tool([])

    await tool.aclose()

    assert tool._embedder._client.is_closed
    assert tool._tickets._client._client.is_closed
