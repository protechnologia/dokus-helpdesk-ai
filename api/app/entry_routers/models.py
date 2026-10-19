from datetime import date as Date
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Modele API wspólne dla kilku tras — kontrakt HTTP, odrębny od modeli domenowych (CLAUDE.md ->
# „Warstwy kodu"): kontrakt na drucie nie może się ruszać przy każdej zmianie domeny, a domena nie
# może wypuszczać na zewnątrz pól wewnętrznych. Modele jednej trasy leżą w jej katalogu.


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
    Jedno źródło odpowiedzi: z jakiego materiału pochodzi („tickets", „docs", „code"), co to jest
    i kiedy powstało. To zgłoszenie albo sekcja, które agent odczytał, albo fragment kodu, który
    zacytował jako przyczynę; powstaje z `cite()` narzędzi, nigdy z deklaracji modelu (zasada 9).
    Źródło z kodu ma w `item_id` ścieżkę pliku z zakresem linii i nie ma daty.
    """

    source:  str         = Field(examples=["tickets"])
    item_id: str         = Field(examples=["33644"])
    title:   str         = Field(examples=["Wysyłka przez ePUAP kończy się błędem"])
    # Zawsze, gdy jest: od niej zależą dezaktualizacja, sprzeczności i sezonowość.
    date:    Date | None = Field(default=None, examples=["2026-03-14"])


class UsageItem(BaseModel):
    """
    Description:
    Zużycie modelu przy jednym żądaniu: liczba wywołań, tokeny i koszt w dolarach. Wraca
    w odpowiedzi każdej trasy opartej na grafie, żeby wołający widział koszt jednej sprawy bez
    sięgania do logów.

    Tokeny są w czterech klasach, tak jak rozliczają je dostawcy: świeże wejście, wyjście oraz
    zapis i odczyt cache promptu. Koszt jest sumą po wszystkich turach modelu. Na atrapach modelu
    wywołania są policzone, a tokeny i koszt wynoszą zero.
    """

    llm_calls:          int   = Field(examples=[3])
    prompt_tokens:      int   = Field(examples=[18200])
    completion_tokens:  int   = Field(examples=[940])
    cache_write_tokens: int   = Field(default=0, examples=[0])
    cache_read_tokens:  int   = Field(default=0, examples=[0])
    cost_usd:           float = Field(examples=[0.0916])


class LogItem(BaseModel):
    """
    Description:
    Jeden krok przebiegu grafu: który węzeł co zrobił. Lista takich wpisów wraca w odpowiedzi
    każdej trasy opartej na grafie, żeby wołający widział przebieg sprawy — kolejność węzłów,
    tury modelu, wywołane narzędzia — bez sięgania do logów.

    `message` jest tekstem dla człowieka i może się zmieniać; nie nadaje się do parsowania. Niesie
    wyłącznie nazwy, liczby i identyfikatory, nigdy treść zgłoszenia ani odpowiedzi modelu.
    """

    node:    str = Field(examples=["agent"])
    message: str = Field(examples=["tura 1: narzędzia: find_tickets_vector; 0,0041 USD"])


class ToolCallItem(BaseModel):
    """
    Description:
    Jedno wywołanie narzędzia w kroku przebiegu: które narzędzie, z jakimi argumentami, co
    dostał model w odpowiedzi i ile to trwało. `call_id` łączy je z turą modelu, która je
    zleciła.

    `result` to tekst, który dostał model, znak w znak: wynik narzędzia w JSON-ie albo błąd
    `{"error": …}`. Argumenty pisze model z tekstu po anonimizacji, a wynik pochodzi z indeksów,
    więc pole niesie materiał, który model czytał, a nie zgłoszenie sprzed anonimizacji.
    """

    call_id:     str            = Field(examples=["call_1"])
    tool:        str            = Field(examples=["find_tickets_vector"])
    arguments:   dict[str, Any] = Field(examples=[{"problem": "Brak przesyłek"}])
    result:      str            = Field(examples=['{"tickets": [], "dropped_below_threshold": 3}'])
    started_at:  datetime       = Field(examples=["2026-10-19T12:03:15.120000Z"])
    duration_ms: float          = Field(examples=[84.2])


class StepItem(BaseModel):
    """
    Description:
    Jeden krok przebiegu grafu w strumieniu trasy (zdarzenie `step`): który węzeł, co zrobił,
    kiedy zaczął i ile trwał. Tura modelu niesie zużycie tej tury, krok narzędzi — wywołania
    z argumentami i wynikami.

    Kroki przychodzą w trakcie przebiegu, więc wołający widzi, co dzieje się teraz; odpowiedź
    trasy przychodzi na końcu, w zdarzeniu `result`. `message` to wpis logu przebiegu — tekst dla
    człowieka, bez treści zgłoszenia, nie do parsowania.
    """

    node:        str                = Field(examples=["agent"])
    message:     str                = Field(examples=["tura 1: narzędzia: find_tickets_vector; …"])
    started_at:  datetime           = Field(examples=["2026-10-19T12:03:14.902000Z"])
    duration_ms: float              = Field(examples=[2140.6])
    usage:       UsageItem | None   = None
    tool_calls:  list[ToolCallItem] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, więc klient parsuje jeden kształt, nie trzy.
    `request_id` pozwala wołającemu podać jedną wartość, która zszywa wszystkie wpisy logu
    nieudanego żądania.
    """

    detail:     str        = Field(examples=["Ticket not found"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])
