from app.agent_graphs import polish
from app.entry_routers.polish.mapping import to_polish_response
from tests._helpers.routers.samples import LOG, USAGE, final_state


def test_the_polished_text_goes_out_with_usage_and_log() -> None:
    """Sprawdza, czy odpowiedź `/polish` złożona ze stanu końcowego grafu niesie poprawiony tekst
    znak w znak, zużycie modelu i log przebiegu w kolejności wpisów.

    Wyłapuje mapowanie, które oddaje inny tekst niż wynik grafu (na przykład notatki z wejścia)
    albo gubi zużycie lub log: wdrożeniowiec dostałby do akceptacji nie to, co napisał model."""
    polished = polish.PolishedText(text="Dzień dobry, przesyłki z e-Doręczeń już docierają.")

    response = to_polish_response(final_state(polish, output=polished))

    assert response.text                        == polished.text
    assert response.usage.llm_calls             == USAGE.calls
    assert [item.node for item in response.log] == [entry.node for entry in LOG]
