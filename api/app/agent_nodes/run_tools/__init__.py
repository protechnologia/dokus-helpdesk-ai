"""
Description:
Węzeł `run_tools`: wykonuje wywołania narzędzi z ostatniej wiadomości modelu — wyłącznie z listy
dozwolonych dla grafu. Argumenty waliduje model zapytania narzędzia; jego wynik jako JSON wraca
do `messages` jako wiadomość `tool`, a źródła z `cite()` odczytów trafiają do `sources`.

Status: atrapa (`FakeRunToolsNode`); właściwy węzeł w p. 10 (CLAUDE.md -> „Plan i TODO").
"""

from app.agent_nodes.run_tools.fake import FakeRunToolsNode, FakeToolAnswer

__all__ = [
    "FakeRunToolsNode",
    "FakeToolAnswer",
]
