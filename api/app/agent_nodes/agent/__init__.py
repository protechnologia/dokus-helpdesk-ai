"""
Description:
Węzeł `agent`: jedna tura modelu — prompt grafu, dotychczasowe wiadomości i definicje narzędzi
z listy dozwolonych (z narzędziem odpowiedzi `respond_<graf>`) idą do `LLMClient`, tura wraca do
`messages`, a `iterations` rośnie o jeden. Graf rozgałęzia po tym, co model wywołał: narzędzie
wiedzy → `run_tools`, `respond_<graf>` → `respond`, sam tekst → błąd formatu; po przekroczeniu
limitu iteracji — `respond`.

Status: atrapa (`FakeAgentNode`); właściwy węzeł w p. 9 (CLAUDE.md -> „Plan").
"""

from app.agent_nodes.agent.fake import FakeAgentNode, tool_call_turn

__all__ = [
    "FakeAgentNode",
    "tool_call_turn",
]
