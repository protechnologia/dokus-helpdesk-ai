import json

from app.agent_graphs.search import TOOL_NAMES, SearchState
from app.engine_llm import ChatMessage
from app.entry_routers.mapping import to_log_items, to_source_items, to_usage_item
from app.entry_routers.search.models import AgentQuery, SearchResponse

# Stan końcowy grafu `search` na odpowiedź `POST /search`. Osobno od trasy, bo tę samą odpowiedź
# złoży każda droga, którą trasa oddaje wynik.

# Pole wyniku wyszukiwania po znaczeniu: ile trafień odciął próg podobieństwa.
DROPPED_FIELD = "dropped_below_threshold"


def to_search_response(
    final: SearchState,  # np. SearchState(…, sources=[SourceRef(…)], output=SearchNotes(…))
) -> SearchResponse:
    """
    Description:
    Zamienia stan końcowy grafu `search` na odpowiedź trasy: źródła z `cite()`, uwagi dla
    wdrożeniowca, zapytania agenta z rozmowy, zużycie modelu i log przebiegu.

    Example args:
        final=SearchState(input_text="ZGŁOSZENIE 41002…", sources=[SourceRef(…), …],
                          output=SearchNotes(internal_notes="## Zgłoszenia historyczne\n- …"))

    Example result:
        SearchResponse(sources=[SourceItem(…), …],
                       internal_notes="## Zgłoszenia historyczne\n- …",
                       queries=[AgentQuery(tool="find_tickets_vector", …,
                                           dropped_below_threshold=0), …])
    """
    response = SearchResponse(
        sources        = to_source_items(final.sources),
        internal_notes = final.output.internal_notes,
        queries        = to_agent_queries(final.messages),
        usage          = to_usage_item(final.usage),
        log            = to_log_items(final.log),
    )

    return response


def to_agent_queries(
    messages: list[ChatMessage],  # np. [ChatMessage(role="assistant", tool_calls=[…]), …]
) -> list[AgentQuery]:
    """
    Description:
    Wyciąga z rozmowy zapytania, które agent wysłał do narzędzi wiedzy — bez wywołania odpowiedzi
    (`respond_search`), które niczego nie szuka. Do wyszukiwania po znaczeniu dokłada licznik
    trafień odciętych progiem, odczytany z wyniku tego wywołania.

    Example args:
        messages=[tool_call_turn("find_tickets_vector", {"problem": "…", "symptoms": "…"}),
                  ChatMessage(role="tool", call_id="call_1", content='{"tickets": […], …}')]

    Example result:
        [AgentQuery(tool="find_tickets_vector", arguments={"problem": "…", "symptoms": "…"},
                    dropped_below_threshold=3)]
    """
    # Wynik wywołania to wiadomość `tool` z jego `call_id`.
    results = {message.call_id: message.content for message in messages if message.role == "tool"}

    queries = [
        AgentQuery(
            tool                    = call.name,
            arguments               = call.arguments,
            dropped_below_threshold = dropped_below_threshold(results.get(call.call_id)),
        )
        for message in messages
        for call in message.tool_calls
        if call.name in TOOL_NAMES
    ]

    return queries


def dropped_below_threshold(
    result_text: str | None,  # np. '{"tickets": [], "dropped_below_threshold": 3}'
) -> int | None:
    """
    Description:
    Czyta z wyniku narzędzia, ile trafień odciął próg podobieństwa. Wynik narzędzia to JSON
    z polami pod nazwami ze schematu, więc licznik jest w nim wprost. Brak wyniku, błąd zamiast
    wyniku albo narzędzie bez progu dają `None`.

    Example args:
        result_text='{"tickets": [], "dropped_below_threshold": 3}'

    Example result:
        3
    """
    # --- wywołanie bez odpowiedzi: tura ucięta limitem tur ---
    if result_text is None:
        return None

    try:
        body = json.loads(result_text)
    except json.JSONDecodeError:  # nie JSON, więc nie wynik narzędzia
        return None

    dropped = body.get(DROPPED_FIELD) if isinstance(body, dict) else None

    return dropped if isinstance(dropped, int) else None
