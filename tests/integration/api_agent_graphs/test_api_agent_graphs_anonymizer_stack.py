import pytest

from app.agent_graphs import gate_close, run_graph
from app.agent_graphs.factory import build_real_graph
from app.engine_anonymization import AnonymizationConfigError, AnonymizerClient
from app.engine_llm import FakeLLMClient
from tests.conftest import anonymizer_url

pytestmark = [pytest.mark.stack, pytest.mark.stack_anonymizer]

# Graf na węzłach właściwych z klientem prawdziwej usługi `anonymizer`. Warunek testu: usługa na
# stacku działa na atrapie silnika (`ANONYMIZATION_ENGINE=fake`, domyślnie w compose). Pełny
# przebieg grafu przez usługę przychodzi z pierwszym prawdziwym silnikiem (CLAUDE.md -> „Plan",
# p. 19.2 i 19.4).


async def test_a_graph_reaches_the_service_and_stops_at_its_fake_engine() -> None:
    """Sprawdza, czy graf bramki zamknięcia złożony z węzłów właściwych wysyła zgłoszenie do
    działającej usługi `anonymizer` przez HTTP i kończy się błędem konfiguracji anonimizatora,
    gdy usługa odpowie atrapą silnika — zanim model dostanie choćby jedno wywołanie.

    Wyłapuje rozjazd kontraktu między klientem a działającym kontenerem (inna ścieżka, inne pola,
    inna nazwa atrapy), którego testy na atrapie transportu nie widzą: klient przestałby
    rozpoznawać atrapę i przepuściłby surowe zgłoszenie do modelu zewnętrznego."""
    llm        = FakeLLMClient()
    anonymizer = AnonymizerClient(base_url=anonymizer_url())
    graph      = build_real_graph(
        graph          = gate_close,
        llm            = llm,
        anonymizer     = anonymizer,
        tools          = (),
        limits         = {},
        max_iterations = 20,
    )

    try:
        with pytest.raises(AnonymizationConfigError):
            await run_graph(graph, gate_close.example_state())
    finally:
        await anonymizer.aclose()

    assert llm.turn_calls == []
