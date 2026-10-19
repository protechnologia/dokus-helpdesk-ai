from types import ModuleType

import pytest

from app.agent_graphs import gate_close, gate_reply
from app.entry_routers.gate.mapping import to_verdict_response
from tests._helpers.routers.samples import BLOCK, LOG, USAGE, final_state

# Grafy bramek: oba oddają werdykt w jednym kształcie.
GATES = [
    pytest.param(gate_close, id="gate_close"),
    pytest.param(gate_reply, id="gate_reply"),
]


@pytest.mark.parametrize("graph", GATES)
def test_the_verdict_goes_out_field_by_field(
    graph: ModuleType,  # wstrzykiwane przez pytest z listy GATES wyżej
) -> None:
    """Sprawdza, czy odpowiedź bramki złożona ze stanu końcowego jej grafu niesie werdykt pole po
    polu — rozstrzygnięcie, uzasadnienie, braki i wskazówkę — dla obu bramek tak samo.

    Wyłapuje mapowanie, które gubi albo przestawia pole werdyktu: helpdesk pokazuje braki
    i wskazówkę we własnym UI, a blokada bez nich to samo „nie" (zasada 10)."""
    response = to_verdict_response(final_state(graph, output=BLOCK), rules_version=1)

    assert response.verdict == BLOCK.verdict
    assert response.reasons == BLOCK.reasons
    assert response.missing == BLOCK.missing
    assert response.hint    == BLOCK.hint


def test_the_response_has_the_gate_and_the_rules_version_given() -> None:
    """Sprawdza, czy odpowiedź bramki ma zawsze furtkę (`overridable` równe `true`) i wersję
    zestawu reguł podaną przez trasę, a nie stałą.

    Wyłapuje odpowiedź bez furtki albo z wersją reguł wpisaną na sztywno: werdykt stałby się
    twardym „nie", a „dlaczego wczoraj przeszło, a dziś nie" byłoby nie do odtworzenia."""
    response = to_verdict_response(final_state(gate_close, output=BLOCK), rules_version=7)

    assert response.overridable   is True
    assert response.rules_version == 7


def test_the_response_carries_usage_and_log_of_the_run() -> None:
    """Sprawdza, czy odpowiedź bramki niesie zużycie modelu i log przebiegu ze stanu końcowego
    grafu, w kolejności wpisów.

    Wyłapuje odpowiedź z zużyciem albo logiem pustym zamiast przebiegu: wołający nie widziałby
    kosztu ani kroków sprawy bez sięgania do logów usługi."""
    response = to_verdict_response(final_state(gate_reply, output=BLOCK), rules_version=1)

    assert response.usage.llm_calls             == USAGE.calls
    assert response.usage.prompt_tokens         == USAGE.prompt_tokens
    assert [item.node for item in response.log] == [entry.node for entry in LOG]
