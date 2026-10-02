"""
Description:
Graf `search` — podobne zgłoszenia i fragmenty instrukcji do nowego zgłoszenia. Agent sam pisze
zapytania w kształcie korpusu i może szukać kilka razy; wynikiem są źródła z `cite()` (`sources`)
i jego zapytania (wywołania narzędzi w `messages`). Kartę zgłoszenia daje graf `parse_ticket`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: `find_tickets`, `find_docs`
(opisy dla modelu obok, jako `.md`); koniec wywołaniem `respond_search` bez argumentów.

Status: na atrapach węzłów (`fake.py`); prompt pętli i pomiar w p. 23 (CLAUDE.md -> „Plan i TODO").
"""

from app.graph.search.fake import build_fake_graph, example_state
from app.graph.search.graph import (
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.search.models import SearchDone
from app.graph.search.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.search.state import SearchState

__all__ = [
    "RESPOND_TOOL_NAME",
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
