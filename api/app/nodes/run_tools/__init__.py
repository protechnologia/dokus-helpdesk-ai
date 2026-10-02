"""
Description:
Węzeł `run_tools`: wykonuje wywołania narzędzi z ostatniej wiadomości modelu — wyłącznie z listy
dozwolonych dla grafu. Argumenty waliduje `query_model` narzędzia; tekst z `render_for_model()`
wraca do `messages` jako wiadomość `tool`, a źródła z `cite()` trafiają do `sources`.

Status: atrapa (`FakeRunTools`); właściwy węzeł w p. 10 (CLAUDE.md -> „Plan i TODO").
"""

from app.nodes.run_tools.fake import FakeRunTools

__all__ = [
    "FakeRunTools",
]
