import httpx
import pytest

from app.agent_graphs import GraphState
from app.agent_nodes import LogEntry
from app.agent_nodes.anonymize.node import AnonymizeNode
from app.engine_anonymization import AnonymizationError, AnonymizedText, FakeAnonymizer
from tests._helpers.anonymization import anonymizer_client_on
from tests._helpers.transport import raising


async def test_the_node_sets_the_anonymized_text() -> None:
    """Sprawdza, czy węzeł anonimizacji przekazuje anonimizatorowi treść wejścia, zapisuje jego
    wynik jako tekst po anonimizacji i dopisuje do dziennika przebiegu jeden wpis z samą długością
    tekstu (24 znaki). Niczego więcej w stanie nie zmienia.

    Wyłapuje węzeł, który zmienia inne pola stanu albo wpisuje do dziennika treść zgłoszenia zamiast
    jej długości."""
    anonymizer = FakeAnonymizer()
    node       = AnonymizeNode(anonymizer)

    update = await node.run(GraphState(input_text="Nie przychodzą przesyłki"))

    assert update == {
        "anonymized": AnonymizedText(text="Nie przychodzą przesyłki"),
        "log":        [LogEntry(node="anonymize", message="zanonimizowano 24 zn.")],
    }
    assert anonymizer.texts == ["Nie przychodzą przesyłki"]


async def test_a_failed_anonymization_stops_the_graph() -> None:
    """Sprawdza, czy błąd anonimizatora wychodzi z węzła jako `AnonymizationError`, bez
    przechwycenia.

    Wyłapuje węzeł, który po nieudanej anonimizacji puściłby przebieg dalej: surowe zgłoszenie
    z danymi klienta trafiłoby wtedy do modelu."""
    # Klient usługi, której nie da się dosięgnąć: zawodzi przy każdym wywołaniu.
    failing = anonymizer_client_on(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(AnonymizationError):
        await AnonymizeNode(failing).run(GraphState(input_text="Jan Kowalski zgłasza…"))
