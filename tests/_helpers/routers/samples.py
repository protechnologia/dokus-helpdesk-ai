"""
Description:
Próbki do testów tras HTTP w `tests/unit/api_entry_routers/` i `tests/functional/`: stany końcowe
grafów z wynikiem, źródłem, zużyciem i logiem, rozmowa grafu `search` z zapytaniami, które trasa
ma z niej wyciągnąć, kroki przebiegu do zdarzeń strumienia i żądania do wszystkich tras grafów.
Dzięki nim plik testu to same testy, a dane, na których stoją asercje, leżą obok helpera.

| co                       | do czego                                                       |
|--------------------------|----------------------------------------------------------------|
| `SOURCE`                 | źródło odczytane przez agenta                                  |
| `USAGE`, `LOG`           | zużycie modelu i log przebiegu w każdym stanie końcowym        |
| `BLOCK`                  | werdykt bramki z uzasadnieniem, brakiem i wskazówką            |
| `CARD`                   | karta zgłoszenia, w której każde pole ma inną wartość          |
| `PROPOSAL`, `NOTES`      | propozycja z treścią dla klienta i same uwagi dla wdrożeniowca |
| `final_state()`          | stan końcowy grafu: przykładowy stan z wynikiem, zużyciem      |
|                          | i logiem                                                       |
| `search_messages()`      | rozmowa `search`: wyszukania, odczyt, tura ucięta i odpowiedź  |
| `SEARCH_QUERIES`         | zapytania agenta, które trasa ma wyciągnąć z tej rozmowy       |
| `TOOL_STEP`, `AGENT_STEP`| krok narzędzi z dwoma wpisami logu i krok tury modelu          |
| `TICKET`                 | zgłoszenie do tras, które je przyjmują                         |
| `GRAPH_REQUESTS`         | trasa grafu → żądanie do niej                                  |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test importuje je z tego modułu.
- Dane są zmyślone, nie kopiowane z korpusu (PII).
- Nowa trasa grafu to wpis w `GRAPH_REQUESTS`: test strumienia sprawdza, że każda trasa
  z wariantem strumienia ma tu swoje żądanie.
"""

from datetime import UTC, date, datetime
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from app.agent_graphs import GraphStep, ToolCallRun, parse_ticket
from app.agent_graphs.search import RESPOND_TOOL_NAME
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.models import LogEntry
from app.agent_tools import SourceRef
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from app.core_model.graphs.verdict import Verdict
from app.engine_llm import ChatMessage, LLMUsage, ToolCall
from app.entry_routers.search.models import AgentQuery

# Źródło odczytane przez agenta: wszystkie cztery pola wypełnione.
SOURCE = SourceRef(
    source  = "tickets",
    item_id = "90001",
    title   = "Nie przychodzą przesyłki z e-Doręczeń",
    date    = date(2026, 9, 1),
)

# Zużycie modelu w stanie końcowym: liczby różne od zera, żeby odpowiedź bez nich było widać.
USAGE = LLMUsage(calls=2, prompt_tokens=1200, completion_tokens=80, cost_usd=0.0123)

# Log przebiegu w stanie końcowym: dwa wpisy, żeby było widać kolejność.
LOG = [
    LogEntry(node="anonymize", message="zanonimizowano 72 zn."),
    LogEntry(node="respond", message="odpowiedź przyjęta"),
]

# Werdykt bramki z każdym polem wypełnionym.
BLOCK = Verdict(
    verdict = "block",
    reasons = ["Nie widać, co zrobiono."],
    hint    = "Dopisz, co zmieniono w konfiguracji.",
)

# Karta zgłoszenia z innym brzmieniem w każdym polu: pole przepisane z sąsiedniego wychodzi wtedy
# jako różnica, a nie przechodzi niezauważone.
CARD = parse_ticket.default_ticket().model_copy(update={"error_codes": ["ERR-4210"]})

# Pełna propozycja: treść dla klienta i uwagi dla wdrożeniowca.
PROPOSAL = Proposal(
    text           = "1. Od kiedy nie przychodzą przesyłki?",
    internal_notes = "1: odcina zacięcie kolejki",
)

# Same uwagi: wariant bez treści dla klienta.
NOTES = ProposalNotes(internal_notes="Szukałem po komunikacie i po objawie — brak podobnych.")

# Argumenty wywołań narzędzi w rozmowie `search`, każde inne, żeby pomyłka wywołań była widoczna.
FIRST_SEARCH  = {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}
SECOND_SEARCH = {"problem": "Brak przesyłek", "symptoms": "błąd pobierania"}
READ          = {"ticket_ids": ["90001"]}
CUT_SEARCH    = {"exact": "nie udało się pobrać"}

# Wyniki wywołań w rozmowie `search`: dwa wyszukania z różnymi licznikami i odczyt bez licznika.
FIRST_RESULT  = '{"tickets": [], "dropped_below_threshold": 3}'
SECOND_RESULT = '{"tickets": ["90001"], "dropped_below_threshold": 0}'
READ_RESULT   = '{"cards": [], "without_card": []}'

# Zapytania agenta, które trasa ma wyciągnąć z `search_messages()`, w kolejności wywołań.
SEARCH_QUERIES = [
    AgentQuery(tool="find_tickets_vector", arguments=FIRST_SEARCH, dropped_below_threshold=3),
    AgentQuery(tool="find_tickets_vector", arguments=SECOND_SEARCH, dropped_below_threshold=0),
    AgentQuery(tool="read_tickets_card", arguments=READ, dropped_below_threshold=None),
    AgentQuery(tool="find_tickets_text", arguments=CUT_SEARCH, dropped_below_threshold=None),
]


def final_state(
    graph:    ModuleType,  # np. search
    **fields: Any,         # np. output=SearchNotes(…), sources=[SOURCE]
) -> BaseModel:
    """
    Description:
    Stan końcowy grafu: przykładowy stan wejściowy grafu z podanymi polami oraz zużyciem `USAGE`
    i logiem `LOG`, tak jakby graf przeszedł do końca.

    Example args:
        graph=search
        fields={"output": SearchNotes(internal_notes="…"), "sources": [SOURCE]}

    Example result:
        SearchState(input_text="…", sources=[SOURCE], output=SearchNotes(…), usage=USAGE, log=LOG)
    """
    state = graph.example_state().model_copy(update={"usage": USAGE, "log": LOG, **fields})

    return state


def search_messages() -> list[ChatMessage]:
    """
    Description:
    Rozmowa grafu `search`: tura z dwoma wyszukaniami po znaczeniu, których wyniki wracają
    w odwrotnej kolejności i niosą różne liczniki odciętych progiem, odczyt kart bez licznika,
    wyszukanie bez wyniku (tura ucięta limitem) i wywołanie odpowiedzi.

    Example args:
        (brak)

    Example result:
        [ChatMessage(role="user", …), ChatMessage(role="assistant", tool_calls=[…]), …]
    """
    two_searches = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="call_1", name="find_tickets_vector", arguments=FIRST_SEARCH),
            ToolCall(call_id="call_2", name="find_tickets_vector", arguments=SECOND_SEARCH),
        ],
    )

    messages = [
        ChatMessage(role="user", content="ZGŁOSZENIE 41002\nOd wczoraj nie przychodzą przesyłki."),
        two_searches,
        ChatMessage(role="tool", call_id="call_2", content=SECOND_RESULT),
        ChatMessage(role="tool", call_id="call_1", content=FIRST_RESULT),
        tool_call_turn("read_tickets_card", READ, call_id="call_3"),
        ChatMessage(role="tool", call_id="call_3", content=READ_RESULT),
        tool_call_turn("find_tickets_text", CUT_SEARCH, call_id="call_4"),
        tool_call_turn(RESPOND_TOOL_NAME, {"internal_notes": "## Zgłoszenia…"}, call_id="call_5"),
    ]

    return messages


# Początek kroków przebiegu w próbkach.
STEP_STARTED_AT = datetime(2026, 10, 19, 12, 3, 15, tzinfo=UTC)

# Krok narzędzi z dwoma wpisami logu i czasami z ogonem do zaokrąglenia.
TOOL_STEP = GraphStep(
    node        = "run_tools",
    started_at  = STEP_STARTED_AT,
    duration_ms = 85.04,
    log         = [
        LogEntry(node="run_tools", message="wywołania: read_tickets_card; źródła: 1"),
        LogEntry(node="run_tools", message="drugi wpis"),
    ],
    tool_calls  = [
        ToolCallRun(
            call_id     = "call_1",
            tool        = "read_tickets_card",
            arguments   = READ,
            result      = READ_RESULT,
            started_at  = STEP_STARTED_AT,
            duration_ms = 84.26,
        ),
    ],
)

# Krok tury modelu: jeden wpis logu, zużycie tury i nazwa narzędzia, o które poprosił model.
AGENT_STEP = GraphStep(
    node            = "agent",
    started_at      = STEP_STARTED_AT,
    duration_ms     = 2140.6,
    log             = [LogEntry(node="agent", message="tura 2: narzędzia: read_tickets_card")],
    usage           = USAGE,
    requested_tools = ["read_tickets_card"],
)

# Zgłoszenie do tras, które je przyjmują; opis ze słowem, którego nie ma w żadnym wpisie logu.
TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}

# Trasa grafu → żądanie do niej. Każda trasa z wariantem strumienia ma tu stać.
GRAPH_REQUESTS: dict[str, dict[str, Any]] = {
    "/search":       TICKET,
    "/gate/close":   TICKET,
    "/gate/reply":   {"ticket_id": "41002", "message": "Dzień dobry, kolejka już działa."},
    "/parse-ticket": TICKET,
    "/suggest":      {**TICKET, "variant": "questions"},
    "/polish":       {"ticket_id": "41002", "text": "kolejka stala, juz dziala"},
}
