import dataclasses

from tests._helpers.scenarios.reading.models.reading_case import ReadingCase


@dataclasses.dataclass(frozen=True)
class ReadingSection:
    """Sekcja zestawu dla jednego grafu: sprawy, które go wymieniają, w kolejności zestawu."""

    graph: str                       # np. "search"
    cases: tuple[ReadingCase, ...]   # sprawy w kolejności zestawu
