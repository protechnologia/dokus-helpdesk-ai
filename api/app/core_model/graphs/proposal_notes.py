from pydantic import BaseModel, ConfigDict, Field


class ProposalNotes(BaseModel):
    """
    Description:
    Propozycja bez treści dla klienta — same uwagi dla wdrożeniowca. Wynik wariantu wymagającego
    źródeł (`suggest_solution`), gdy agent nie odczytał żadnego źródła.

    Do czego:
    Bez źródeł treść dla klienta byłaby napisana „z głowy", więc węzeł `respond` ją odrzuca
    (zasada 9), a uwagi zostawia: mówią wdrożeniowcowi, czego agent szukał i co wykluczył. Osobny
    model zamiast `text: None` w `Proposal`, żeby schemat dla modelu został ścisły — model nie może
    sam oddać propozycji bez treści, gdy źródła ma.
    """

    model_config = ConfigDict(extra="forbid")

    internal_notes: str = Field(examples=["Szukałem po komunikacie i po objawie — brak podobnych."])
