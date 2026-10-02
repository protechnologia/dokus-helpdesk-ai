"""
Description:
Graf `suggest_questions` — wariant generacji „Jakie pytania zadać": lista pytań dla wdrożeniowca,
oparta na podobnych sprawach, które agent sam znajduje. Wynik to `Proposal`; źródła z `cite()`
leżą w `sources`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: `find_tickets`, `find_docs`
(opisy dla modelu obok, jako `.md`); koniec wywołaniem `respond_suggest_questions`. Działa przy
pustym indeksie (`REQUIRES_HITS = False`).

Status: na atrapach węzłów (`fake.py`); prompt przeniesiony z dawnego
`text/prompt_suggest_questions_*`, przemierzenie na modelu docelowym w p. 25 (CLAUDE.md ->
„Plan i TODO").
"""

from app.graph.suggest_questions.fake import build_fake_graph, example_state
from app.graph.suggest_questions.graph import (
    REQUIRES_HITS,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.suggest_questions.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.suggest_questions.state import SuggestQuestionsState

__all__ = [
    "REQUIRES_HITS",
    "RESPOND_TOOL_NAME",
    "TOOL_NAMES",
    "SuggestQuestionsState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
