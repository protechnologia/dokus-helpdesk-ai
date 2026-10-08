from pydantic import BaseModel, Field

from app.entry_routers.models import LogItem, SourceItem, TicketRequest, UsageItem


class SuggestRequest(TicketRequest):
    """
    Description:
    Wejście `POST /suggest`: zgłoszenie i wariant odpowiedzi, czyli guzik, który kliknął człowiek.
    Wariant jest parametrem, nie trasą — nowy guzik to nowy katalog grafu bez zmiany routera.
    Nieznany wariant to 422, nigdy cichy fallback na domyślny.
    """

    variant: str = Field(examples=["questions", "solution", "handoff"])


class SuggestResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /suggest` — ten sam kształt dla każdego wariantu: tekst propozycji dla
    klienta, uwagi dla wdrożeniowca, źródła i wariant, którym propozycja powstała. Wariant bez
    narzędzi wiedzy wraca z pustą listą źródeł, i to jest informacja, nie brak danych.

    `internal_notes` to uwagi, które czyta wdrożeniowiec, a klient ich nie dostaje: nazwy z kodu,
    notatki przy pytaniach, czego materiał nie rozstrzyga. Pusty napis znaczy, że uwag nie ma.

    `text` jest puste (`null`), gdy wariant wymaga źródeł (`requires_hits`), a agent żadnego nie
    odczytał: treści dla klienta wtedy nie ma, cokolwiek model napisał (zasada 9), a uwagi
    zostają — mówią, czego agent szukał i co wykluczył. To poprawna odpowiedź („nowy typ
    problemu"), nie błąd — stąd 200 z pustą listą źródeł.
    """

    variant:        str              = Field(examples=["questions"])
    text:           str | None       = Field(examples=["1. Od kiedy nie przychodzą przesyłki? …"])
    internal_notes: str              = Field(examples=["1: odcina zacięcie kolejki (zgł. 41002)"])
    sources:        list[SourceItem] = Field(default_factory=list)
    usage:          UsageItem
    log:            list[LogItem]    = Field(default_factory=list)


class VariantInfo(BaseModel):
    """
    Description:
    Jeden wariant odpowiedzi do narysowania jako guzik: nazwa do `/suggest`, etykieta dla
    człowieka i czy działa przy pustym indeksie.
    """

    name:          str  = Field(examples=["questions"])
    label:         str  = Field(examples=["Jakie pytania zadać"])
    requires_hits: bool = Field(examples=[False])


class VariantsResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /variants`: warianty z rejestru grafów — UI helpdesku rysuje guziki z tej listy,
    a nie z własnej, zaszytej.
    """

    variants: list[VariantInfo] = Field(default_factory=list)
