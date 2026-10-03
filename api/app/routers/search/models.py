from typing import Any

from pydantic import BaseModel, Field

from app.routers.models import SourceItem


class AgentQuery(BaseModel):
    """
    Description:
    Jedno zapytanie, które agent wysłał do narzędzia wiedzy. To jest dziś „odczyt zgłoszenia":
    dziwną listę trafień najczęściej tłumaczy to, o co agent zapytał, a nie samo wyszukiwanie.
    """

    tool:      str            = Field(examples=["find_tickets_vector"])
    arguments: dict[str, Any] = Field(examples=[{"problem": "Brak przesyłek"}])


class SearchResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /search`: znalezione źródła i zapytania agenta. Brak źródeł to 200 z pustą
    listą — „nowy typ problemu" jest poprawną odpowiedzią dla 47% korpusu.
    """

    sources: list[SourceItem] = Field(default_factory=list)
    queries: list[AgentQuery] = Field(default_factory=list)
