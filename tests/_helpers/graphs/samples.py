"""
Description:
Próbki do testu kontraktu grafów (`tests/unit/api_agent_graphs/test_api_agent_graphs_contract.py`):
wynik inny niż domyślny dla atrapy każdego grafu, oraz do testu kroku przebiegu
(`test_api_agent_graphs_graph_step.py`): zmiany stanu tury modelu i kroku narzędzi z rozmową,
w której dwie tury mają wywołanie o tym samym identyfikatorze. Dzięki nim plik testu to same
testy, a dane, na których stoją asercje, leżą obok helpera grafów.

| co                    | do czego                                                          |
|-----------------------|-------------------------------------------------------------------|
| `BLOCK`               | werdykt bramki inny niż domyślny: blokada z brakiem i wskazówką   |
| `GIVEN_OUTPUTS`       | wynik podawany atrapie każdego grafu, którego wynik ma treść      |
| `FIRST_TURN`,         | dwie tury modelu z wywołaniem o tym samym `call_id`               |
| `SECOND_TURN`         |                                                                   |
| `STEP_STARTED_AT`,    | początek, czas i zużycie podawane krokowi                         |
| `STEP_USAGE`          |                                                                   |
| `READ_TIMING`,        | pomiar czasu odczytu z drugiej tury i wynik, który dostał model   |
| `READ_RESULT`         |                                                                   |
| `two_turns()`         | rozmowa po kroku narzędzi drugiej tury                            |
| `agent_update()`      | zmiana stanu tury modelu: tura, zużycie, wpis w logu              |
| `run_tools_update()`  | zmiana stanu kroku narzędzi: wynik, wpis w logu, pomiar czasu     |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test importuje je z tego modułu.
- Graf, którego brakuje w `GIVEN_OUTPUTS`, wywraca test atrapy: nowy graf trzeba tu dopisać
  świadomie.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.agent_graphs import parse_ticket
from app.agent_graphs.polish import PolishedText
from app.agent_graphs.search import SearchNotes
from app.agent_nodes import LogEntry, ToolTiming
from app.agent_nodes.agent import tool_call_turn
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.verdict import Verdict
from app.engine_llm import ChatMessage, LLMUsage

# Werdykt bramki inny niż domyślny: blokada z uzasadnieniem, brakiem i wskazówką.
BLOCK = Verdict(
    verdict = "block",
    reasons = ["Nie widać, co było przyczyną."],
    missing = ["przyczyna"],
    hint    = "Dopisz, dlaczego usługa stanęła.",
)

# Wynik inny niż domyślny, podawany atrapie każdego grafu, którego wynik ma treść: test sprawdza,
# że atrapa oddaje dokładnie ten, a nie swój domyślny.
GIVEN_OUTPUTS: dict[str, BaseModel] = {
    "gate_close":        BLOCK,
    "gate_reply":        BLOCK,
    "parse_ticket":      parse_ticket.default_ticket().model_copy(update={"cause": "brak"}),
    "polish":            PolishedText(text="Dzień dobry, przesyłki już docierają."),
    "search":            SearchNotes(internal_notes="Zgłoszenia: żadnej nie znaleziono."),
    "suggest_handoff":   Proposal(text="Przekazujemy sprawę do dalszych prac.", internal_notes=""),
    "suggest_questions": Proposal(
        text           = "1. Od kiedy nie przychodzą przesyłki?",
        internal_notes = "Ad. 1. odcina zacięcie kolejki",
    ),
    "suggest_solution":  Proposal(
        text           = "Kroki do wykonania: 1. Prosimy o restart usługi.",
        internal_notes = "- Odpowiedź stoi na jednym zgłoszeniu.",
    ),
}

# Dwie tury modelu, każda z wywołaniem `call_1`: atrapa modelu numeruje wywołania od nowa w każdej
# turze, więc identyfikator nie wskazuje wywołania w całej rozmowie, tylko w jednej turze.
FIRST_TURN  = tool_call_turn("find_tickets_vector", {"problem": "Brak przesyłek", "symptoms": "—"})
SECOND_TURN = tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]})

# Początek kroku i zużycie tury modelu, podawane krokowi wprost.
STEP_STARTED_AT = datetime(2026, 10, 19, 12, 3, 15, tzinfo=UTC)
STEP_USAGE      = LLMUsage(calls=1, prompt_tokens=4820, completion_tokens=96, cost_usd=0.0321)

# Pomiar czasu odczytu kart z drugiej tury.
READ_TIMING = ToolTiming(call_id="call_1", started_at=STEP_STARTED_AT, duration_ms=84.2)

# Wynik odczytu kart, który dostał model.
READ_RESULT = '{"cards": [{"ticket_id": "90001"}], "without_card": []}'


def two_turns() -> list[ChatMessage]:
    """
    Description:
    Rozmowa po kroku narzędzi drugiej tury: zgłoszenie, wyszukanie z wynikiem i odczyt z wynikiem,
    oba wywołania pod `call_1`.

    Example args:
        (brak)

    Example result:
        [ChatMessage(role="user", …), FIRST_TURN, ChatMessage(role="tool", …), SECOND_TURN, …]
    """
    messages = [
        ChatMessage(role="user", content="ZGŁOSZENIE 41002\nNie przychodzą przesyłki."),
        FIRST_TURN,
        ChatMessage(role="tool", call_id="call_1", content='{"tickets": []}'),
        SECOND_TURN,
        ChatMessage(role="tool", call_id="call_1", content=READ_RESULT),
    ]

    return messages


def agent_update() -> dict[str, Any]:
    """
    Description:
    Zmiana stanu, którą oddaje węzeł `agent` po drugiej turze: tura z wywołaniem odczytu, licznik
    tur, zużycie tury i wpis w logu.

    Example args:
        (brak)

    Example result:
        {"messages": [SECOND_TURN], "iterations": 2, "usage": STEP_USAGE, "log": [LogEntry(…)]}
    """
    update = {
        "messages":   [SECOND_TURN],
        "iterations": 2,
        "usage":      STEP_USAGE,
        "log":        [LogEntry(node="agent", message="tura 2: narzędzia: read_tickets_card")],
    }

    return update


def run_tools_update() -> dict[str, Any]:
    """
    Description:
    Zmiana stanu, którą oddaje węzeł `run_tools` po odczycie z drugiej tury: wynik odczytu, wpis
    w logu i pomiar czasu.

    Example args:
        (brak)

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", …)], "log": […],
         "tool_timings": [READ_TIMING]}
    """
    update = {
        "messages":     [ChatMessage(role="tool", call_id="call_1", content=READ_RESULT)],
        "log":          [LogEntry(node="run_tools", message="wywołania: read_tickets_card")],
        "tool_timings": [READ_TIMING],
    }

    return update
