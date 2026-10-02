"""
Description:
Graf `parse_ticket` — karta zgłoszenia: wątek zamieniony na `ParsedTicket` promptem parsującym,
tym samym, którym powstaje korpus (zasada 7). Używa go `/parse-ticket`, powrót zamkniętych
zgłoszeń do korpusu (p. 30) i masowy import (p. 31).

Przebieg: anonymize → agent → respond. Bez narzędzi i — jako jedyny graf — bez narzędzia
odpowiedzi: prompt parsujący każe zwrócić JSON w tekście, a to kontrakt artefaktu; rozstrzygnięcie
w p. 24. Własnego promptu też nie ma: `system_prompt()` i `user_prompt()` sięgają do `text/`.

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
from app.graph.parse_ticket.state import ParseTicketState

__all__ = [
    "STATE",
    "TOOL_NAMES",
    "ParseTicketState",
    "build_fake_graph",
    "build_graph",
    "default_ticket",
    "example_state",
    "model_tools",
    "system_prompt",
    "user_prompt",
]
