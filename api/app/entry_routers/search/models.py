from typing import Any

from pydantic import BaseModel, Field

from app.entry_routers.models import LogItem, SourceItem, UsageItem


class AgentQuery(BaseModel):
    """
    Description:
    Jedna pozycja listy `queries` w odpowiedzi `POST /search`: wywołanie narzędzia, które model
    wykonał, szukając materiału do zgłoszenia — które narzędzie i z jakimi argumentami. Lista
    wraca do wołającego przez HTTP, żeby widział, o co model pytał bazę.

    Po co mu to: gdy źródła w odpowiedzi są nietrafione albo puste, przyczyna zwykle leży
    w zapytaniu modelu — źle nazwany problem, zgubiony kod błędu — a nie w samym wyszukiwaniu.
    Z listy źródeł tego nie widać.

    `dropped_below_threshold` mówi, ile trafień tego wyszukiwania odciął próg podobieństwa.
    Dzięki niemu pusta lista źródeł nie wygląda tak samo przy pustym indeksie (zero) i przy
    progu, który wszystko wyciął (więcej niż zero). Podają go tylko wyszukiwania po znaczeniu;
    przy pozostałych narzędziach i przy wywołaniu zakończonym błędem pole jest puste.
    """

    tool:                    str            = Field(examples=["find_tickets_vector"])
    arguments:               dict[str, Any] = Field(examples=[{"problem": "Brak przesyłek"}])
    dropped_below_threshold: int | None     = Field(default=None, examples=[3])


class SearchResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /search`: znalezione źródła i zapytania agenta. Brak źródeł to 200 z pustą
    listą — „nowy typ problemu" jest poprawną odpowiedzią dla 47% korpusu.
    """

    sources: list[SourceItem] = Field(default_factory=list)
    queries: list[AgentQuery] = Field(default_factory=list)
    usage:   UsageItem
    log:     list[LogItem]    = Field(default_factory=list)
