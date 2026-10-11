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
    Odpowiedź `POST /search`: rozpoznanie do zgłoszenia — źródła, uwagi dla wdrożeniowca
    i zapytania agenta. Brak źródeł to 200 z pustą listą — „nowy typ problemu" jest poprawną
    odpowiedzią dla 47% korpusu.

    `internal_notes` to uwagi, które czyta wdrożeniowiec: czy przeczytane sprawy zgadzają się co
    do przyczyny, co mówią instrukcje i kod aplikacji, czego agent szukał bez skutku i co w kodzie
    wykluczył. To lekki Markdown: cztery sekcje z nagłówkiem `##` (Zgłoszenia historyczne,
    Instrukcje i dokumentacja, Kod aplikacji, Nie znaleziono), a w nich lista albo zwykły tekst.
    Pisze je model, a lista źródeł obok powstaje z odczytów, nie z uwag. Nigdy nie są puste:
    przy pustej liście źródeł mówią, czego agent szukał. Pole nazywa się jak uwagi w `/suggest`,
    bo czyta je ta sama osoba.
    """

    sources:        list[SourceItem] = Field(default_factory=list)
    internal_notes: str              = Field(examples=["## Zgłoszenia historyczne\n- 41002: …"])
    queries:        list[AgentQuery] = Field(default_factory=list)
    usage:          UsageItem
    log:            list[LogItem]    = Field(default_factory=list)
