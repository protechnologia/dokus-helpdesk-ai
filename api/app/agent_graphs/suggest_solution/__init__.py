"""
Description:
Graf `suggest_solution` — wariant generacji „Gotowa odpowiedź": rozwiązanie dla klienta, złożone
wyłącznie z podobnych spraw, które agent sam znajduje. Wynik to `Proposal`; źródła z `cite()`
leżą w `sources`.

Przebieg: anonymize → pętla agent ⇄ run_tools → respond. Narzędzia: wyszukiwania i spis oddają
identyfikatory, odczyty treść (opisy dla modelu w katalogach narzędzi); koniec wywołaniem
`respond_suggest_solution`. Bez odczytanych źródeł nie ma treści dla klienta
(`REQUIRES_HITS = True`): węzeł `respond` odrzuca ją wtedy, cokolwiek model napisał, i zostawia
same uwagi dla wdrożeniowca (`without_sources()`, wynik `ProposalNotes`).

Status: węzły właściwe z fabryki grafów, atrapa w `fake.py`; prompt przeniesiony z dawnego
`core_text/prompt_suggest_solution_*`, przemierzenie na modelu docelowym w p. 26 (CLAUDE.md ->
„Plan").
"""

from app.agent_graphs.suggest_solution.fake import build_fake_graph, example_state
from app.agent_graphs.suggest_solution.graph import (
    LABEL,
    REQUIRES_HITS,
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    respond_node,
    system_prompt,
    user_prompt,
    without_sources,
)
from app.agent_graphs.suggest_solution.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.suggest_solution.state import SuggestSolutionState

__all__ = [
    "LABEL",
    "REQUIRES_HITS",
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "SuggestSolutionState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_node",
    "respond_tool",
    "system_prompt",
    "user_prompt",
    "without_sources",
]
