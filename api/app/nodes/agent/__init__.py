"""
Description:
Węzeł `agent`: jedna tura modelu — prompt grafu, dotychczasowe wiadomości i definicje narzędzi
z listy dozwolonych idą do `LLMClient`, odpowiedź (tekst albo wywołania narzędzi) wraca do
`messages`, a `iterations` rośnie o jeden. Na tej odpowiedzi graf decyduje: dalej pętla czy
odpowiedź; po przekroczeniu limitu iteracji — odpowiedź.

Status: atrapa (`FakeAgent`); właściwy węzeł w p. 7 (CLAUDE.md -> „Plan i TODO").
"""

from app.nodes.agent.fake import FakeAgent, tool_call_turn

__all__ = [
    "FakeAgent",
    "tool_call_turn",
]
