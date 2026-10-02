import pytest
from pydantic import BaseModel

from app.anonymization import AnonymizationError, AnonymizedText, Anonymizer, FakeAnonymizer
from app.nodes.anonymize.node import AnonymizeNode


class State(BaseModel):
    """Najmniejszy stan grafu, jakiego potrzebuje ten węzeł."""

    input_text: str
    anonymized: AnonymizedText | None = None


class FailingAnonymizer(Anonymizer):
    """Anonimizator, który zawsze się wywraca — `FakeAnonymizer` nie umie odtworzyć porażki."""

    async def anonymize(
        self,
        text: str,  # np. "Jan Kowalski…"
    ) -> AnonymizedText:
        """
        Description:
        Zgłasza błąd anonimizacji przy każdym wywołaniu.

        Example args:
            text="Jan Kowalski zgłasza…"

        Example result:
            (zawsze AnonymizationError)

        Raises:
            AnonymizationError: zawsze
        """
        raise AnonymizationError("nie udało się zanonimizować")


async def test_the_node_sets_the_anonymized_text() -> None:
    """Wejście grafu → `anonymized` z wyniku anonimizatora; nic innego węzeł nie zmienia."""
    anonymizer = FakeAnonymizer()
    node       = AnonymizeNode(anonymizer)

    update = await node.run(State(input_text="Nie przychodzą przesyłki"))

    assert update     == {"anonymized": AnonymizedText(text="Nie przychodzą przesyłki")}
    assert anonymizer.texts == ["Nie przychodzą przesyłki"]


async def test_a_failed_anonymization_stops_the_graph() -> None:
    """Błąd anonimizatora → wychodzi z węzła: fail-closed, surowy tekst nie idzie dalej."""
    with pytest.raises(AnonymizationError):
        await AnonymizeNode(FailingAnonymizer()).run(State(input_text="Jan Kowalski zgłasza…"))
