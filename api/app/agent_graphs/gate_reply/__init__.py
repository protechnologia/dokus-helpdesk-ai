"""
Description:
Graf `gate_reply` — bramka wysyłki: czy wiadomość do klienta nie łamie reguł wysyłki (prośba
o hasło, potoczne słownictwo, forma zwrotu…). Wynik to `Verdict`, ten sam kształt co w bramce
zamknięcia; blokadę egzekwuje helpdesk, nie my (zasada 11).

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy i bez `run_tools`. Jedyne narzędzie
modelu to `respond_gate_reply` (`respond_tool.py`). Reguły wysyłki przychodzą w stanie (`rules`)
i trafiają do oddzielonej sekcji danych w turze użytkownika.

Status: na atrapach węzłów (`fake.py`); prompt to szkielet, treść i pomiar w p. 22 (CLAUDE.md ->
„Plan").
"""

from app.agent_graphs.gate_reply.fake import build_fake_graph, example_state
from app.agent_graphs.gate_reply.graph import (
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.agent_graphs.gate_reply.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.gate_reply.state import GateReplyState

__all__ = [
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "GateReplyState",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
