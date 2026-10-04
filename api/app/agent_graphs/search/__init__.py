"""
Description:
Graf `search` — podobne zgłoszenia i fragmenty instrukcji do nowego zgłoszenia. Agent sam pisze
zapytania w kształcie korpusu i może szukać kilka razy; wynikiem są źródła z `cite()` (`sources`),
czyli to, co agent odczytał, i jego wywołania narzędzi (`messages`). Kartę nowego zgłoszenia
daje graf `parse_ticket`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: wyszukiwania i spis oddają
identyfikatory, odczyty treść (opisy dla modelu w katalogach narzędzi); koniec wywołaniem
`respond_search` bez argumentów.

Status: na atrapach węzłów (`fake.py`); prompt pętli i pomiar w p. 23 (CLAUDE.md -> „Plan").
"""

from app.agent_graphs.search.fake import build_fake_graph, example_state
from app.agent_graphs.search.graph import (
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.agent_graphs.search.models import SearchDone
from app.agent_graphs.search.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.search.state import SearchState

__all__ = [
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "SearchDone",
    "SearchState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
