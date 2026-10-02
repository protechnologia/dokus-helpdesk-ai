"""
Description:
Graf `polish` — „Popraw": notatki wdrożeniowca przepisane na poprawną formę, bez zmiany treści
(zasada 9). Jedyny graf, który zwraca tekst do wysłania (`PolishedText`), zawsze do akceptacji
człowieka. Do potwierdzenia, czy zostaje w zakresie (CLAUDE.md -> „Plan i TODO", p. 28).

Przebieg: anonymize → agent → respond. Bez narzędzi wiedzy i bez `run_tools`. Jedyne narzędzie
modelu to `respond_polish` (`respond_tool.py`). Zasady stylu przychodzą w stanie (`rules`)
i trafiają do oddzielonej sekcji danych w turze użytkownika.

Status: na atrapach węzłów (`fake.py`); prompt to szkielet, treść i pomiar w p. 28.
"""

from app.graph.polish.fake import build_fake_graph, example_state
from app.graph.polish.graph import (
    TOOL_NAMES,
    build_graph,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.graph.polish.models import PolishedText
from app.graph.polish.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.polish.state import PolishState

__all__ = [
    "RESPOND_TOOL_NAME",
    "TOOL_NAMES",
    "PolishState",
    "PolishedText",
    "build_fake_graph",
    "build_graph",
    "example_state",
    "model_tools",
    "respond_tool",
    "system_prompt",
    "user_prompt",
]
