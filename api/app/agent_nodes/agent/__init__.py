"""
Description:
Węzeł `agent`: jedna tura modelu — prompt grafu, dotychczasowe wiadomości i definicje narzędzi
z listy dozwolonych (z narzędziem odpowiedzi `respond_<graf>`) idą do `LLMClient`, tura wraca do
`messages`, a `iterations` rośnie o jeden. Dokąd przebieg idzie dalej, rozstrzyga graf
(`route_after_agent`): narzędzia wiedzy → `run_tools`, `respond_<graf>`, sam tekst albo wyczerpany
limit tur → `respond`.

| plik      | co zawiera                                                               |
|-----------|--------------------------------------------------------------------------|
| `node.py` | `AgentNode` — węzeł właściwy, pyta model przez `LLMClient`               |
| `fake.py` | `FakeAgentNode` — oddaje zaplanowane tury; `tool_call_turn()` je buduje  |
| `base.py` | `AgentNodeBase` — część wspólna obu: nazwa i zapis tury w stanie grafu   |

Status: węzeł właściwy na atrapie modelu (`FakeLLMClient`); tura z narzędziami u prawdziwych
dostawców w p. 17 (CLAUDE.md -> „Plan").
"""

from app.agent_nodes.agent.fake import FakeAgentNode, tool_call_turn
from app.agent_nodes.agent.node import AgentNode

__all__ = [
    "AgentNode",
    "FakeAgentNode",
    "tool_call_turn",
]
