"""
Description:
Graf `search` — rozpoznanie do zgłoszenia w trzech materiałach: historycznych zgłoszeniach,
instrukcjach i kodzie aplikacji. Agent sam pisze zapytania i może szukać kilka razy; wynikiem są
źródła z `cite()` (`sources`), czyli to, co agent odczytał albo zacytował z kodu jako przyczynę,
jego wywołania narzędzi (`messages`) i uwagi dla wdrożeniowca (`SearchNotes`). Na tej podstawie
człowiek decyduje, czy dopytać klienta, odpowiedzieć, czy przekazać sprawę. Kartę nowego
zgłoszenia daje graf `parse_ticket`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: wyszukiwania i spis oddają
identyfikatory, odczyty treść (opisy dla modelu w katalogach narzędzi); koniec wywołaniem
`respond_search` z uwagami.

Status: węzły właściwe z fabryki grafów, atrapa w `fake.py`; prompt sprawdzony sondą na
zmyślonych sprawach (p. 70), pomiar na prawdziwych w p. 23 (CLAUDE.md -> „Plan").
"""

from app.agent_graphs.search.fake import build_fake_graph, example_state
from app.agent_graphs.search.graph import (
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    respond_node,
    system_prompt,
    user_prompt,
)
from app.agent_graphs.search.models import SearchNotes
from app.agent_graphs.search.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.search.state import SearchState

__all__ = [
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "SearchNotes",
    "SearchState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_node",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
