from pydantic import Field

from app.agent_graphs.base import GraphState
from app.model.gate_verdict import Verdict


class GateCloseState(GraphState):
    """
    Description:
    Stan grafu `gate_close`: pola wspólne z `GraphState` plus reguły zamknięcia i werdykt.

    Bez `sources` — bramka nie ma narzędzi wiedzy, więc nie ma czego cytować. Brak reguł albo
    pusta lista to błąd walidacji: bramka bez reguł nie ma czego sprawdzać, a przepuszczenie
    wyglądałoby jak „wszystko OK".
    """

    rules:  list[str]      = Field(min_length=1)  # reguły zamknięcia: dane klienta, do oddzielonej sekcji promptu
    output: Verdict | None = None                 # werdykt bramki; ustawia węzeł `respond`
