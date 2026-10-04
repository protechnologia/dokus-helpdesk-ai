from pydantic import BaseModel, Field

from app.entry_routers.models import SourceItem, TicketRequest, UsageItem


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
    Odpowiedź `POST /suggest` — ten sam kształt dla każdego wariantu: tekst propozycji, źródła
    i wariant, którym powstała. Wariant bez narzędzi wiedzy wraca z pustą listą źródeł, i to jest
    informacja, nie brak danych.
    """

    variant: str              = Field(examples=["questions"])
    text:    str              = Field(examples=["1. Od kiedy nie przychodzą przesyłki? …"])
    sources: list[SourceItem] = Field(default_factory=list)
    usage:   UsageItem


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
