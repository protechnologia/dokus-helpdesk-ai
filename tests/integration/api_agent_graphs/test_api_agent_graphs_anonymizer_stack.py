import pytest

from app.agent_graphs import gate_close, run_graph
from app.agent_graphs.factory import (
    build_function_graph,
    build_real_graph,
    close_process_anonymizer,
    process_anonymizer,
)
from app.agent_graphs.gate_close.fake import DEFAULT_VERDICT
from app.agent_nodes.respond import RespondError
from app.engine_anonymization import AnonymizerClient
from app.engine_llm import FakeLLMClient
from tests._helpers.anonymization import RAW_TEXT, SENSITIVE
from tests.conftest import anonymizer_url

pytestmark = [pytest.mark.stack, pytest.mark.stack_anonymizer]

# Grafy na kliencie prawdziwej usługi `anonymizer`. Warunek testów: usługa na stacku działa na
# silniku `agent` (domyślnie w compose) z osiągalnym modelem anonimizującym (`LLM_ANONYMIZATION_*`
# w `.env`). Usługa na atrapie silnika daje w pierwszym teście błąd konfiguracji anonimizatora,
# który ją nazywa.


async def test_a_graph_reaches_the_service_and_the_model_gets_anonymized_text() -> None:
    """Sprawdza, czy graf bramki zamknięcia złożony z węzłów właściwych wysyła zgłoszenie do
    działającej usługi `anonymizer` przez HTTP, a model generujący (tu atrapa) dostaje tekst bez
    danych osobowych zgłoszenia — imienia, nazwiska i telefonu.

    Wyłapuje rozjazd kontraktu między klientem a działającym kontenerem (inna ścieżka, inne pola,
    nazwa silnika brana za atrapę) i wdrożenie, w którym usługa nie dostała modelu: surowe
    zgłoszenie poszłoby wtedy do modelu zewnętrznego albo każdy graf stawałby na 503."""
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
    state = gate_close.example_state().model_copy(update={"input_text": RAW_TEXT})

    try:
        # Atrapa modelu bez scenariusza odpowiada samym tekstem, więc graf kończy się odmową
        # odpowiedzi; liczy się to, co model dostał, zanim odmówił.
        with pytest.raises(RespondError):
            await run_graph(graph, state)
    finally:
        await anonymizer.aclose()

    sent = " ".join(message.content or "" for call in llm.turn_calls for message in call.messages)

    assert llm.turn_calls
    for fragment in SENSITIVE:
        assert fragment not in sent


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
