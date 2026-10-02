from datetime import date as Date
from typing import Any, Literal

from pydantic import BaseModel, Field

# Modele API — kontrakt HTTP, odrębny od modeli domenowych (CLAUDE.md -> „Warstwy kodu"): kontrakt
# na drucie nie może się ruszać przy każdej zmianie domeny, a domena nie może wypuszczać na zewnątrz
# pól wewnętrznych. Każde pole wychodzące jest tu wypisane jawnie.


class TicketComment(BaseModel):
    """
    Description:
    Jeden komentarz wątku zgłoszenia, tak jak przysyła go helpdesk.

    Wymagane jest tylko `body`. `role` i `created_at` są oznaczane w prompcie, ale model ma ważyć
    treść ponad etykiety — ta baza ma udokumentowane przypadki obu błędnych (autor odwrócony
    w kategorii „Automat mailowy"). Przysłane pomagają, brakujące kosztują niewiele.
    """

    body:       str = Field(examples=["Proszę sprawdzić uprawnienia certyfikatu."])
    role:       str = Field(default="", examples=["konsultant", "klient"])
    created_at: str = Field(default="", examples=["2026-06-23 12:01:21"])


class TicketRequest(BaseModel):
    """
    Description:
    Zgłoszenie w kształcie, w jakim helpdesk już je trzyma — wejście `/search`, `/gate/close`,
    `/parse-ticket` i `/suggest`.

    Wymagane tylko `ticket_id` i `body`: id wiąże odpowiedź ze zgłoszeniem w logach i w przyszłym
    feedbacku, a `body` JEST treścią. Reszta opisuje zgłoszenie, nie sterując odpowiedzią, więc
    jej żądanie podnosiłoby koszt wpięcia bez zysku.
    """

    ticket_id: str                 = Field(examples=["41002"])
    body:      str                 = Field(examples=["Nie mogę wysłać pisma przez ePUAP."])
    # Brak daty znaczy „dziś": zgłoszenie w toku jest z definicji świeże.
    date:      Date | None         = Field(default=None, examples=["2026-08-19"])
    subject:   str                 = Field(default="", examples=["Błąd wysyłki"])
    # Jedyna znacząca wartość to „Automat mailowy" — wątki z cytowaną historią do czyszczenia.
    category:  str                 = Field(default="", examples=["Automat mailowy", "Błąd"])
    comments:  list[TicketComment] = Field(default_factory=list)


class SourceItem(BaseModel):
    """
    Description:
    Jedno źródło odpowiedzi: które narzędzie co znalazło, z jakim podobieństwem i kiedy materiał
    powstał. Powstaje z `cite()` narzędzi, nigdy z deklaracji modelu (zasada 9).
    """

    source:  str         = Field(examples=["find_tickets"])
    item_id: str         = Field(examples=["33644"])
    title:   str         = Field(examples=["Wysyłka przez ePUAP kończy się błędem"])
    score:   float       = Field(examples=[0.87])
    # Zawsze, gdy jest: od niej zależą dezaktualizacja, sprzeczności i sezonowość.
    date:    Date | None = Field(default=None, examples=["2026-03-14"])


class AgentQuery(BaseModel):
    """
    Description:
    Jedno zapytanie, które agent wysłał do narzędzia wiedzy. To jest dziś „odczyt zgłoszenia":
    dziwną listę trafień najczęściej tłumaczy to, o co agent zapytał, a nie samo wyszukiwanie.
    """

    tool:      str            = Field(examples=["find_tickets"])
    arguments: dict[str, Any] = Field(examples=[{"problem": "Brak przesyłek"}])


class SearchResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /search`: znalezione źródła i zapytania agenta. Brak źródeł to 200 z pustą
    listą — „nowy typ problemu" jest poprawną odpowiedzią dla 47% korpusu.
    """

    sources: list[SourceItem] = Field(default_factory=list)
    queries: list[AgentQuery] = Field(default_factory=list)


class TicketCard(BaseModel):
    """
    Description:
    Odpowiedź `POST /parse-ticket`: karta zgłoszenia, czyli sparsowane pola w kształcie korpusu.
    Własny model, a nie `ParsedTicket` przepuszczony wprost — model domenowy nie wychodzi przez
    HTTP.

    Niesie tekst klienta (nazwiska bywają w `problem`), co jest dopuszczalne, bo wołającym jest
    helpdesk, do którego zgłoszenie należy — i jest powodem, by endpoint stał za uwierzytelnianiem
    (p. 36).
    """

    ticket_id:         str       = Field(examples=["41002"])
    date:              Date      = Field(examples=["2026-08-19"])
    component:         str       = Field(examples=["ePUAP"])
    problem:           str       = Field(examples=["Wysyłka kończy się błędem"])
    symptoms:          str       = Field(examples=["Komunikat o braku sieci"])
    error_codes:       list[str] = Field(default_factory=list, examples=[["ERR-4210"]])
    cause:             str       = Field(examples=["brak"])
    solution:          str       = Field(examples=["brak"])
    resolution:        str       = Field(examples=["naprawione"])
    questions_summary: str       = Field(examples=["brak"])


class VerdictResponse(BaseModel):
    """
    Description:
    Odpowiedź obu bramek (`/gate/close`, `/gate/reply`) — jeden kształt, więc wołający pisze jedną
    obsługę. Werdykt jest danymi, nie prozą: `missing` helpdesk pokazuje jako listę we własnym UI.

    `overridable` jest zawsze `true`: furtka dla człowieka jest częścią kontraktu, nie obejściem
    (zasada 10), a blokadę egzekwuje helpdesk, nie my (zasada 11). `rules_version` mówi, którą
    wersją zestawu reguł wydano werdykt.
    """

    verdict:       Literal["pass", "block"] = Field(examples=["block"])
    reasons:       list[str]                = Field(default_factory=list, examples=[["Brak."]])
    missing:       list[str]                = Field(default_factory=list, examples=[["przyczyna"]])
    hint:          str                      = Field(default="", examples=["Dopisz, co zmieniono."])
    overridable:   bool                     = Field(default=True, examples=[True])
    rules_version: int                      = Field(examples=[1])


class GateReplyRequest(BaseModel):
    """
    Description:
    Wejście `POST /gate/reply`: wiadomość do klienta, którą wdrożeniowiec chce wysłać, i zgłoszenie,
    którego dotyczy (do logów).
    """

    ticket_id: str = Field(examples=["41002"])
    message:   str = Field(min_length=1, examples=["Dzień dobry, proszę podać hasło do skrzynki."])


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


class PolishRequest(BaseModel):
    """
    Description:
    Wejście `POST /polish`: notatki wdrożeniowca do przepisania i zgłoszenie, którego dotyczą
    (do logów).
    """

    ticket_id: str = Field(examples=["41002"])
    text:      str = Field(min_length=1, examples=["przesylki juz ida, kolejka stala"])


class PolishResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /polish`: ten sam sens w poprawnej formie — zawsze do akceptacji człowieka,
    nigdy w miejsce oryginału automatycznie.
    """

    text: str = Field(examples=["Dzień dobry, przesyłki z e-Doręczeń już docierają…"])


class HealthResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /health`. Celowo nic o konfiguracji — sonda żywotności jest osiągalna dla
    każdego, kto dosięgnie usługi, więc nie może zdradzać dostawców, adresów ani modeli.
    """

    status: str = Field(examples=["ok"])


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, więc klient parsuje jeden kształt, nie trzy.
    `request_id` pozwala wołającemu podać jedną wartość, która zszywa wszystkie wpisy logu
    nieudanego żądania.
    """

    detail:     str        = Field(examples=["Ticket not found"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])
