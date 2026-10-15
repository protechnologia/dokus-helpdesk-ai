import dataclasses

from tests._helpers.scenarios.search.models.search_case import SearchCase


@dataclasses.dataclass(frozen=True)
class SearchSection:
    """Sekcja zestawu dla jednego grafu: sprawy w kolejności zestawu."""

    graph: str                     # np. "search"
    cases: tuple[SearchCase, ...]  # sprawy w kolejności zestawu
