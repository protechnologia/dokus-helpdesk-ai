from app.agent_graphs import parse_ticket
from app.entry_routers.parse_ticket.mapping import to_ticket_card
from tests._helpers.routers.samples import CARD, LOG, USAGE, final_state


def test_every_card_field_goes_out_unchanged() -> None:
    """Sprawdza, czy karta w odpowiedzi `/parse-ticket` ma każde pole karty z grafu, każde pod
    swoją nazwą i z tą samą wartością, a wersji słownika rozstrzygnięć nie ma.

    Wyłapuje pole zgubione albo przepisane z sąsiedniego (`cause` z `solution`) oraz wyciek
    wersji słownika, która jest metadaną artefaktu: helpdesk dostałby kartę niezgodną z tym, co
    trafiłoby do korpusu."""
    response = to_ticket_card(final_state(parse_ticket, output=CARD))

    card_fields = response.model_dump(exclude={"usage", "log"})

    assert card_fields == CARD.model_dump(exclude={"resolution_vocabulary_version"})


def test_the_card_carries_usage_and_log_of_the_run() -> None:
    """Sprawdza, czy karta w odpowiedzi niesie zużycie modelu i log przebiegu ze stanu końcowego
    grafu, w kolejności wpisów.

    Wyłapuje odpowiedź z zużyciem albo logiem pustym zamiast przebiegu: wołający nie widziałby
    kosztu ani kroków sprawy bez sięgania do logów usługi."""
    response = to_ticket_card(final_state(parse_ticket, output=CARD))

    assert response.usage.llm_calls             == USAGE.calls
    assert [item.node for item in response.log] == [entry.node for entry in LOG]
