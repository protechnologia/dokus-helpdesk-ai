"""
Description:
Graf `suggest_solution` — wariant generacji „Gotowa odpowiedź": rozwiązanie dla klienta, złożone
wyłącznie z podobnych spraw, które agent sam znajduje. Wynik to `Proposal`; źródła z `cite()`
leżą w `sources`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: `find_tickets`, `find_docs`
(opisy dla modelu obok, jako `.md`); koniec wywołaniem `respond_suggest_solution`. Bez trafień nie
ma propozycji (`REQUIRES_HITS = True`, egzekwuje `respond` — p. 11).

Status: na atrapach węzłów (`fake.py`); prompt przeniesiony z
`text/prompt_suggest_solution_system.md`, przemierzenie na modelu docelowym w p. 26 (CLAUDE.md ->
„Plan i TODO").
"""

from app.graph.suggest_solution.fake import build_fake_graph, example_state
from app.graph.suggest_solution.graph import (
    REQUIRES_HITS,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.suggest_solution.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.suggest_solution.state import SuggestSolutionState

__all__ = [
    "REQUIRES_HITS",
    "RESPOND_TOOL_NAME",
    "TOOL_NAMES",
    "SuggestSolutionState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
