import dataclasses

from tests._helpers.scenarios.code.models.code_case import CodeCase


@dataclasses.dataclass(frozen=True)
class CodeSection:
    """Sekcja zestawu dla jednego grafu: sprawy w kolejności zestawu."""

    graph: str                     # np. "search"
    cases: tuple[CodeCase, ...]  # sprawy w kolejności zestawu
