import dataclasses
from collections.abc import Sequence

from app.agent_tools import AgentTool


@dataclasses.dataclass(frozen=True)
class LiveCase:
    """Sprawa do przepuszczenia przez graf na żywym modelu: wejście, reguły klienta i narzędzia."""

    text:  str                                # wejście grafu, np. "ZGŁOSZENIE 90101…"
    rules: Sequence[str] | None = None        # reguły klienta; None — reguły z przykładu grafu
    tools: Sequence[AgentTool] | None = None  # narzędzia sprawy; None — `fake_agent_tools()`
