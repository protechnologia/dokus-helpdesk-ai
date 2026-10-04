import pytest

from app.agent_graphs import GraphState
from app.agent_nodes import LogEntry
from app.agent_nodes.anonymize.node import AnonymizeNode
from app.engine_anonymization import AnonymizationError, AnonymizedText, Anonymizer, FakeAnonymizer


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
    """Wejście grafu → `anonymized` z wyniku anonimizatora i wpis w logu z samą długością tekstu;
    nic innego węzeł nie zmienia."""
    anonymizer = FakeAnonymizer()
    node       = AnonymizeNode(anonymizer)

    update = await node.run(GraphState(input_text="Nie przychodzą przesyłki"))

    assert update == {
        "anonymized": AnonymizedText(text="Nie przychodzą przesyłki"),
        "log":        [LogEntry(node="anonymize", message="zanonimizowano 24 zn.")],
    }
    assert anonymizer.texts == ["Nie przychodzą przesyłki"]


async def test_a_failed_anonymization_stops_the_graph() -> None:
    """Błąd anonimizatora → wychodzi z węzła: fail-closed, surowy tekst nie idzie dalej."""
    with pytest.raises(AnonymizationError):
        await AnonymizeNode(FailingAnonymizer()).run(GraphState(input_text="Jan Kowalski zgłasza…"))
