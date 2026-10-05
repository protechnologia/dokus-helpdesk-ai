from pydantic import Field

from app.agent_graphs.base import GraphState
from app.core_model.graphs.verdict import Verdict


class GateReplyState(GraphState):
    """
    Description:
    Stan grafu `gate_reply`: pola wspólne z `GraphState` plus reguły wysyłki i werdykt.
    `input_text` to wiadomość do klienta, którą wdrożeniowiec chce wysłać.

    Bez `sources` — bramka nie ma narzędzi wiedzy. Brak reguł albo pusta lista to błąd walidacji:
    bramka bez reguł nie ma czego sprawdzać, a przepuszczenie wyglądałoby jak „wszystko OK".
    """

    rules:  list[str]      = Field(min_length=1)  # reguły wysyłki: dane klienta, do oddzielonej sekcji promptu
    output: Verdict | None = None                 # werdykt bramki; ustawia węzeł `respond`
