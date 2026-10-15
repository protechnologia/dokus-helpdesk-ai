import dataclasses

from tests._helpers.scenarios.solution.models.solution_case import SolutionCase


@dataclasses.dataclass(frozen=True)
class SolutionSection:
    """Sekcja zestawu dla jednego grafu: sprawy w kolejności zestawu."""

    graph: str                       # np. "suggest_solution"
    cases: tuple[SolutionCase, ...]  # sprawy w kolejności zestawu
