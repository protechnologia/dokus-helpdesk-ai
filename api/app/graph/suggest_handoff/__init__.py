"""
Description:
Graf `suggest_handoff` — wariant generacji „Przekazanie sprawy": informacja dla klienta, że
zgłoszenie przechodzi do dalszych prac po stronie serwisu, niosąca co sprawdzono i czego brakuje.
Wynik to `Proposal`.

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy — przekazanie opiera się na wątku, więc
wraca z pustą listą źródeł i działa przy pustym indeksie (`REQUIRES_HITS = False`). Jedyne
narzędzie modelu to `respond_suggest_handoff` (`respond_tool.py`).

Status: na atrapach węzłów (`fake.py`); prompt to szkielet, treść i pomiar w p. 27 (CLAUDE.md ->
„Plan i TODO").
"""

from app.graph.suggest_handoff.fake import build_fake_graph, example_state
from app.graph.suggest_handoff.graph import (
    REQUIRES_HITS,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.suggest_handoff.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.suggest_handoff.state import SuggestHandoffState

__all__ = [
    "REQUIRES_HITS",
    "RESPOND_TOOL_NAME",
    "TOOL_NAMES",
    "SuggestHandoffState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
