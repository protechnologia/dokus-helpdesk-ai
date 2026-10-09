from datetime import date as Date

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


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, więc klient parsuje jeden kształt, nie trzy.
    `request_id` pozwala wołającemu podać jedną wartość, która zszywa wszystkie wpisy logu
    nieudanego żądania.
    """

    detail:     str        = Field(examples=["Ticket not found"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])
