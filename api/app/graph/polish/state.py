from pydantic import Field

from app.graph.base import GraphState
from app.graph.polish.models import PolishedText


class PolishState(GraphState):
    """
    Description:
    Stan grafu `polish`: pola wspólne z `GraphState` plus zasady stylu i poprawiony tekst.
    `input_text` to notatki wdrożeniowca do przepisania.

    Bez `sources` — „Popraw" nie sięga do bazy. Brak zasad albo pusta lista to błąd walidacji,
    jak przy bramkach: bez zasad nie ma według czego poprawiać.
    """

    rules:  list[str]           = Field(min_length=1)  # zasady stylu: dane klienta, do oddzielonej sekcji promptu
    output: PolishedText | None = None                 # poprawiony tekst; ustawia węzeł `respond`
