import dataclasses

from tests._helpers.scenarios.handoff.models.handoff_case import HandoffCase


@dataclasses.dataclass(frozen=True)
class HandoffSection:
    """Sekcja zestawu dla grafu przekazania sprawy: sprawy w kolejności zestawu."""

    graph: str                      # np. "suggest_handoff"
    cases: tuple[HandoffCase, ...]  # sprawy w kolejności zestawu
