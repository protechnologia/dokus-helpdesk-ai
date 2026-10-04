"""
Description:
Graf `gate_close` — bramka zamknięcia: czy z treści zgłoszenia wynika, co było problemem i co
zostało zrobione. Wynik to `Verdict`; blokadę egzekwuje helpdesk, nie my (zasada 11).

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy i bez `run_tools` — bramka działa przy
pustym indeksie i padniętym embedderze (CLAUDE.md -> „Warstwa API"). Jedyne narzędzie modelu to
`respond_gate_close`, którym wydaje werdykt (`respond_tool.py`). Reguły zamknięcia przychodzą
w stanie (`rules`) i trafiają do oddzielonej sekcji danych w turze użytkownika.

Status: na atrapach węzłów (`fake.py`); prompt to szkielet, treść i pomiar w p. 21 (CLAUDE.md ->
„Plan").
"""

from app.agent_graphs.gate_close.fake import build_fake_graph, example_state
from app.agent_graphs.gate_close.graph import (
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.agent_graphs.gate_close.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.gate_close.state import GateCloseState

__all__ = [
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "GateCloseState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
