"""
Description:
Węzeł `agent`: jedna tura modelu — prompt grafu, dotychczasowe wiadomości i definicje narzędzi
z listy dozwolonych (z narzędziem odpowiedzi `respond_<graf>`) idą do `LLMClient`, tura wraca do
`messages`, a `iterations` rośnie o jeden. Graf rozgałęzia po tym, co model wywołał: narzędzie
wiedzy → `run_tools`, `respond_<graf>` → `respond`, sam tekst → błąd formatu; po przekroczeniu
limitu iteracji — `respond`.

Status: atrapa (`FakeAgent`); właściwy węzeł w p. 9 (CLAUDE.md -> „Plan i TODO").
"""

from app.nodes.agent.fake import FakeAgent, tool_call_turn

__all__ = [
    "FakeAgent",
    "tool_call_turn",
]
