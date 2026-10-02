from typing import Any

from pydantic import BaseModel

from app.anonymization import Anonymizer
from app.nodes.base import Node


class AnonymizeNode(Node):
    """
    Description:
    Pierwszy węzeł każdego grafu: zamienia `input_text` na `AnonymizedText`. Tylko ten tekst
    widzi dalej model zewnętrzny.

    Fail-closed: błąd anonimizatora nie jest tu łapany — graf się zatrzymuje, zamiast puścić dalej
    tekst bez anonimizacji. Atrapy tego węzła nie ma (CLAUDE.md -> „Plan i TODO", p. 4): w testach
    dostaje `FakeAnonymizer`, czyli atrapę zależności, nie węzła.
    """

    name = "anonymize"

    def __init__(
        self,
        anonymizer: Anonymizer,  # np. FakeAnonymizer()
    ):
        """
        Description:
        Przyjmuje anonimizator wybrany przez fabrykę.

        Example args:
            anonymizer=FakeAnonymizer()

        Example result:
            AnonymizeNode gotowy do wpięcia w graf
        """
        self._anonymizer = anonymizer

    async def run(
        self,
        state: BaseModel,  # np. stan grafu z input_text="Nie przychodzą przesyłki…"
    ) -> dict[str, Any]:
        """
        Description:
        Anonimizuje `input_text` i ustawia `anonymized`. Do logu idzie sama długość tekstu.

        Example args:
            state=SuggestSolutionState(input_text="Nie przychodzą przesyłki z e-Doręczeń")

        Example result:
            {"anonymized": AnonymizedText(text="Nie przychodzą przesyłki z e-Doręczeń"),
             "log": [LogEntry(node="anonymize", message="zanonimizowano 37 zn.")]}

        Raises:
            AnonymizationError: tekstu nie da się bezpiecznie zanonimizować
        """
        anonymized = await self._anonymizer.anonymize(state.input_text)

        update = {
            "anonymized": anonymized,
            "log":        [self.log_entry(f"zanonimizowano {len(state.input_text)} zn.")],
        }

        return update
