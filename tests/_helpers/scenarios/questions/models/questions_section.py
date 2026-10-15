import dataclasses

from tests._helpers.scenarios.questions.models.questions_case import QuestionsCase


@dataclasses.dataclass(frozen=True)
class QuestionsSection:
    """Sekcja zestawu dla jednego grafu: sprawy w kolejności zestawu."""

    graph: str                        # np. "suggest_questions"
    cases: tuple[QuestionsCase, ...]  # sprawy w kolejności zestawu
