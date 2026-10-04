"""
Description:
Węzeł `run_tools`: wykonuje wywołania narzędzi z ostatniej wiadomości modelu — wyłącznie z listy
dozwolonych dla grafu. Argumenty waliduje `query_model` narzędzia; tekst z `render_for_model()`
wraca do `messages` jako wiadomość `tool`, a źródła z `cite()` trafiają do `sources`.

Status: atrapa (`FakeRunToolsNode`); właściwy węzeł w p. 10 (CLAUDE.md -> „Plan i TODO").
"""

from app.agent_nodes.run_tools.fake import FakeRunToolsNode

__all__ = [
    "FakeRunToolsNode",
]
