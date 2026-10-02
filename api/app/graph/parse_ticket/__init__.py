"""
Description:
Graf `parse_ticket` — karta zgłoszenia: wątek zamieniony na `ParsedTicket` promptem parsującym.
Ten sam prompt zbuduje korpus przy masowym imporcie (p. 31), więc to KONTRAKT ARTEFAKTU (zasada 7):
`prompt_system.md`, `prompt_user.md` i `respond_tool.md` pod testem-strażnikiem.

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy; kartę model oddaje narzędziem
`respond_parse_ticket` (`respond_tool.py`) bez pól `FILLED_BY_GRAPH` — tożsamość, datę i wersję
słownika dokłada graf ze stanu.

Status: na atrapach węzłów (`fake.py`); prompt na modelu docelowym w p. 24 (CLAUDE.md -> „Plan
i TODO").
"""

from app.graph.parse_ticket.fake import build_fake_graph, default_ticket, example_state
from app.graph.parse_ticket.graph import (
    STATE,
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.parse_ticket.respond_tool import FILLED_BY_GRAPH, RESPOND_TOOL_NAME, respond_tool
from app.graph.parse_ticket.state import ParseTicketState

__all__ = [
    "FILLED_BY_GRAPH",
    "RESPOND_TOOL_NAME",
    "STATE",
    "TOOL_NAMES",
    "ParseTicketState",
    "build_fake_graph",
    "build_graph",
    "default_ticket",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
