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
    Jedno źródło odpowiedzi: które narzędzie co znalazło, z jakim podobieństwem i kiedy materiał
    powstał. Powstaje z `cite()` narzędzi, nigdy z deklaracji modelu (zasada 9).
    """

    source:  str         = Field(examples=["tickets"])
    item_id: str         = Field(examples=["33644"])
    title:   str         = Field(examples=["Wysyłka przez ePUAP kończy się błędem"])
    score:   float       = Field(examples=[0.87])
    # Zawsze, gdy jest: od niej zależą dezaktualizacja, sprzeczności i sezonowość.
    date:    Date | None = Field(default=None, examples=["2026-03-14"])


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, więc klient parsuje jeden kształt, nie trzy.
    `request_id` pozwala wołającemu podać jedną wartość, która zszywa wszystkie wpisy logu
    nieudanego żądania.
    """

    detail:     str        = Field(examples=["Ticket not found"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])
