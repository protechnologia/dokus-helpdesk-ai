from datetime import datetime

from pydantic import BaseModel, Field

from app.core_model.tickets.ticket_import_failure import TicketImportFailure


class TicketsImportReport(BaseModel):
    """
    Description:
    Co zrobił jeden przebieg masowego importu (p. 31): ile zgłoszeń było w eksporcie, ile wypadło
    z zakresu i dlaczego, ile kart powstało, ile kosztowały i które zgłoszenia się nie udały.

    Do czego:
    Import to jedyny drogi przebieg w projekcie (zasada 7), więc raport niesie to, co pozwala go
    odtworzyć i ocenić: model i skrót promptu parsującego, którymi powstały karty, koszt i listę
    błędów do wznowienia. Serwis wypełnia go w trakcie przebiegu i oddaje komendzie po każdym
    zgłoszeniu, a na końcu zapisuje w katalogu korpusu. Treści zgłoszeń w nim nie ma — same
    numery, liczby i nazwy.

    Liczniki zakresu są rozłączne: zgłoszenie niezamknięte wypada przed sprawdzeniem kanału,
    a zgłoszenie z kartą liczy się w `already_carded` tylko wtedy, gdy przeszło oba wcześniejsze
    sprawdzenia. Bez limitu razem z `todo` sumują się do `files`; z limitem `todo` to tylko
    zgłoszenia do zrobienia w tym przebiegu.
    """

    started_at:     datetime                  = Field(examples=["2026-11-13T10:15:00Z"])
    # Koniec przebiegu, także przerwanego; `None`, dopóki trwa.
    finished_at:    datetime | None           = Field(default=None, examples=["2026-11-13T11:13Z"])
    # Model generujący z konfiguracji; ten, który odpowiedział, zapisuje karta w `parser_model`.
    model:          str                       = Field(examples=["gpt-6.1-sol"])
    # Skrót promptu parsującego (`parse_ticket.prompt_digest()`): ta sama wartość w dwóch
    # raportach znaczy ten sam kontrakt artefaktu.
    prompt_digest:  str                       = Field(examples=["3f1c9a…"])
    files:          int                       = Field(examples=[1955])
    skipped_open:   int                       = Field(examples=[61])
    skipped_mail:   int                       = Field(examples=[136])
    already_carded: int                       = Field(examples=[0])
    todo:           int                       = Field(examples=[1758])
    parsed:         int                       = Field(default=0, examples=[1756])
    # Ile zapisanych kart model ocenił jako przydatne (`useful`); te przejdą filtr jakości.
    useful:         int                       = Field(default=0, examples=[1201])
    failed:         list[TicketImportFailure] = Field(default_factory=list)
    # Koszt kart zapisanych w tym przebiegu; wywołania zgłoszeń zakończonych błędem w nim nie ma.
    cost_usd:       float                     = Field(default=0.0, examples=[9.1234])
    # Rozkład pola `component` kart zapisanych w tym przebiegu — rozjazd zapisu tej samej usługi
    # widać w nim, zanim obejmie cały korpus.
    components:     dict[str, int]            = Field(default_factory=dict)

    @property
    def done(self) -> int:
        """
        Description:
        Ile zgłoszeń przebieg już skończył, kartą albo błędem.

        Example args:
            (brak)

        Example result:
            120
        """
        return self.parsed + len(self.failed)
