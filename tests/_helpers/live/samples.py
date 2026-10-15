"""
Description:
Próbki do testów samego helpera żywego modelu (`tests/unit/test_live_usage_report.py`,
`tests/unit/test_live_graphs.py`): zmyślone zużycie dwóch spraw, przebieg i rozmowa jednej sprawy
oraz reguły klienta. Dzięki nim pliki testów to same testy, a dane, na których stoją asercje,
leżą obok helpera, którego dotyczą.

| co             | do czego                                                              |
|----------------|-----------------------------------------------------------------------|
| `SEARCH_USAGE` | zużycie sprawy z pętlą: pięć wywołań, wszystkie cztery klasy tokenów  |
| `GATE_USAGE`   | zużycie sprawy bez pętli: jedno wywołanie, bez cache                  |
| `RUN_LOG`      | przebieg sprawy: trzy tury modelu, wpisy pozostałych węzłów           |
| `RUN_MESSAGES` | rozmowa tej samej sprawy: wywołania narzędzi i ich wyniki, też błąd   |
| `RULES`        | reguły klienta podawane sprawie bramki                                |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- `RUN_LOG` i `RUN_MESSAGES` opisują tę samą sprawę: tura w przebiegu ma swoją turę w rozmowie,
  więc zmiana jednego bez drugiego rozjeżdża test wywołań pod turami.
"""

import json

from app.agent_nodes.models import LogEntry
from app.agent_tools.base import error_as_json
from app.engine_llm import ChatMessage, LLMUsage, ToolCall

# Zużycie sprawy z pętlą narzędzi: wszystkie cztery klasy tokenów, żeby suma raportu sprawdzała
# każdą.
SEARCH_USAGE = LLMUsage(
    calls              = 5,
    prompt_tokens      = 412,
    cache_write_tokens = 8120,
    cache_read_tokens  = 25010,
    completion_tokens  = 640,
    cost_usd           = 0.0270,
)

# Zużycie sprawy bez pętli: jedno wywołanie, bez cache.
GATE_USAGE = LLMUsage(calls=1, prompt_tokens=900, completion_tokens=60, cost_usd=0.0031)

# Przebieg jednej zmyślonej sprawy: model szuka w kodzie, czyta plik (ścieżką, której nie ma, więc
# dostaje błąd) i odpowiada. Trzy tury modelu, trzy wpisy węzła `agent`.
RUN_LOG = [
    LogEntry(node="anonymize", message="zanonimizowano"),
    LogEntry(node="agent",     message="tura 1: narzędzia: find_code_text; 0,0041 USD"),
    LogEntry(node="run_tools", message="wywołania: find_code_text; źródła: 0"),
    LogEntry(node="agent",     message="tura 2: narzędzia: read_code_file; 0,0038 USD"),
    LogEntry(node="run_tools", message="wywołania: read_code_file; źródła: 0; błędy: 1"),
    LogEntry(node="agent",     message="tura 3: narzędzia: respond_search; 0,0020 USD"),
    LogEntry(node="respond",   message="odpowiedź przyjęta"),
]

# Rozmowa tej samej sprawy: wywołanie narzędzia w każdej turze modelu i wynik pod nim; narzędzie
# odpowiedzi wyniku nie ma.
RUN_MESSAGES = [
    ChatMessage(role="user", content="=== ZGŁOSZENIE ===\nBrak sekwencji numeracji dla roku 2026"),
    ChatMessage(role="assistant", tool_calls=[
        ToolCall(call_id="call_1", name="find_code_text", arguments={"exact": "Brak sekwencji"}),
    ]),
    ChatMessage(
        role    = "tool",
        call_id = "call_1",
        content = json.dumps({"lines": [{"path": "src/a.php"}], "omitted_over_limit": 0}),
    ),
    ChatMessage(role="assistant", tool_calls=[
        ToolCall(call_id="call_2", name="read_code_file", arguments={"path": "src/brak.php"}),
    ]),
    ChatMessage(
        role    = "tool",
        call_id = "call_2",
        content = error_as_json("nie ma takiego pliku w kodzie aplikacji: src/brak.php"),
    ),
    ChatMessage(role="assistant", tool_calls=[
        ToolCall(call_id="call_3", name="respond_search", arguments={}),
    ]),
]

# Reguły klienta sprawy bramki: jedna reguła wystarcza, żeby odróżnić podane reguły od przykładu.
RULES = ["Wiadomość nie prosi klienta o hasło ani login."]
