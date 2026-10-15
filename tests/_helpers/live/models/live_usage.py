import dataclasses

from app.agent_nodes.models import LogEntry
from app.engine_llm import ChatMessage, LLMUsage


@dataclasses.dataclass(frozen=True)
class LiveUsage:
    """Zużycie jednej sprawy na żywym modelu, zgłoszone przez test."""

    label:    str                      # np. "graf search"
    usage:    LLMUsage                 # wywołania, tokeny i koszt całej sprawy
    log:      tuple[LogEntry, ...]     # wpisy przebiegu grafu; puste poza sprawami grafów
    messages: tuple[ChatMessage, ...]  # rozmowa z modelem; pusta, gdy test jej nie zgłosił
