"""
Description:
Graf `suggest_handoff` — wariant generacji „Przekazanie sprawy": informacja dla klienta, że
zgłoszenie przechodzi do dalszych prac po stronie serwisu, niosąca co sprawdzono i czego brakuje.
Wynik to `Proposal`.

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy — przekazanie opiera się na wątku, więc
wraca z pustą listą źródeł i działa przy pustym indeksie (`REQUIRES_HITS = False`). Jedyne
narzędzie modelu to `respond_suggest_handoff` (`respond_tool.py`).

Status: węzły właściwe z fabryki grafów, atrapa w `fake.py`; prompt to szkielet, treść
i pomiar w p. 27 (CLAUDE.md -> „Plan").
"""

from app.agent_graphs.suggest_handoff.fake import build_fake_graph, example_state
from app.agent_graphs.suggest_handoff.graph import (
    LABEL,
    REQUIRES_HITS,
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    respond_node,
    system_prompt,
    user_prompt,
)
from app.agent_graphs.suggest_handoff.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.suggest_handoff.state import SuggestHandoffState

__all__ = [
    "LABEL",
    "REQUIRES_HITS",
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "SuggestHandoffState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_node",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
