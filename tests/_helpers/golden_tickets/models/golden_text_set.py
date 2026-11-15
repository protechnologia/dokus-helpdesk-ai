from dataclasses import dataclass

from tests._helpers.golden_tickets.models.golden_text_query import GoldenTextQuery


@dataclass(frozen=True)
class GoldenTextSet:
    """Zestaw tekstowy z pliku: liczniki z metryczki, zapytania z celem i zapytania bez celu."""

    counts:      dict[str, int]         # liczniki z metryczki: `queries`, `distractors`
    queries:     list[GoldenTextQuery]  # zapytania z celem, w kolejności z pliku
    distractors: list[GoldenTextQuery]  # zapytania bez celu, w kolejności z pliku
