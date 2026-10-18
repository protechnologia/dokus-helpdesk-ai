import pytest

from app.agent_graphs import gate_close, run_graph
from app.agent_graphs.factory import (
    build_function_graph,
    build_real_graph,
    close_process_anonymizer,
    process_anonymizer,
)
from app.agent_graphs.gate_close.fake import DEFAULT_VERDICT
from app.engine_anonymization import AnonymizationConfigError, AnonymizerClient
from app.engine_llm import FakeLLMClient
from tests.conftest import anonymizer_url

pytestmark = [pytest.mark.stack, pytest.mark.stack_anonymizer]

# Grafy na kliencie prawdziwej usługi `anonymizer`. Warunek testów: usługa na stacku działa na
# atrapie silnika (`ANONYMIZATION_ENGINE=fake`, domyślnie w compose). Pełny przebieg grafu na
# węzłach właściwych przez usługę przychodzi z pierwszym prawdziwym silnikiem (CLAUDE.md ->
# „Plan", p. 19.5).


async def test_a_graph_reaches_the_service_and_stops_at_its_fake_engine() -> None:
    """Sprawdza, czy graf bramki zamknięcia złożony z węzłów właściwych wysyła zgłoszenie do
    działającej usługi `anonymizer` przez HTTP i kończy się błędem konfiguracji anonimizatora,
    gdy usługa odpowie atrapą silnika, a klient nie ma na nią zgody (tak jak przy prawdziwym
    modelu) — zanim model dostanie choćby jedno wywołanie.

    Wyłapuje rozjazd kontraktu między klientem a działającym kontenerem (inna ścieżka, inne pola,
    inna nazwa atrapy), którego testy na atrapie transportu nie widzą: klient przestałby
    rozpoznawać atrapę i przepuściłby surowe zgłoszenie do modelu zewnętrznego."""
    llm        = FakeLLMClient()
    anonymizer = AnonymizerClient(base_url=anonymizer_url(), fake_engine_allowed=False)
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


async def test_with_the_fake_model_the_factory_graph_goes_through_the_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy przy atrapie modelu graf bramki zamknięcia z fabryki grafów — ten, który
    dostaje trasa — przechodzi przez działającą usługę `anonymizer` do końca i oddaje werdykt
    atrapy.

    Wyłapuje rozjazd między fabryką a działającym kontenerem, którego atrapa transportu nie
    pokaże: klient z fabryki, który odmawia atrapy silnika przy atrapie modelu albo nie umie
    przeczytać odpowiedzi prawdziwej usługi, kładłby każdą trasę grafu na świeżo postawionym
    stacku."""
    monkeypatch.setenv("ANONYMIZATION_BASE_URL", anonymizer_url())
    process_anonymizer.cache_clear()

    try:
        final = await run_graph(build_function_graph(gate_close), gate_close.example_state())
    finally:
        await close_process_anonymizer()

    assert final.output == DEFAULT_VERDICT
