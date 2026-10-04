"""
Description:
Węzeł `run_tools`: wykonuje wywołania narzędzi z ostatniej wiadomości modelu — wyłącznie z listy
dozwolonych dla grafu. Argumenty waliduje model zapytania narzędzia; jego wynik jako JSON wraca
do `messages` jako wiadomość `tool`, a źródła z `cite()` odczytów trafiają do `sources`.
Wywołanie ponad limit swojego narzędzia (`limits.py`, wartości z `AGENT_MAX_CALLS_*`) dostaje
błąd zamiast wyniku.

Status: atrapa (`FakeRunToolsNode`); właściwy węzeł w p. 10 (CLAUDE.md -> „Plan i TODO").
"""

from app.agent_nodes.run_tools.fake import FakeRunToolsNode, FakeToolAnswer
from app.agent_nodes.run_tools.limits import calls_over_limit, limit_exceeded_text

__all__ = [
    "FakeRunToolsNode",
    "FakeToolAnswer",
    "calls_over_limit",
    "limit_exceeded_text",
]
