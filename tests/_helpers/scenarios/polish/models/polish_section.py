import dataclasses

from tests._helpers.scenarios.polish.models.polish_case import PolishCase


@dataclasses.dataclass(frozen=True)
class PolishSection:
    """Sekcja zestawu dla grafu „Popraw”: wersja zasad stylu, pod którą napisano sprawy,
    i sprawy."""

    graph:         str                     # np. "polish"
    rules_version: int                     # np. 1 — wersja zestawu domyślnego zasad stylu
    cases:         tuple[PolishCase, ...]  # sprawy w kolejności zestawu
