from typing import Literal

from pydantic import BaseModel, Field

from app.entry_routers.models import LogItem, UsageItem

# Co trasa zrobiła ze zgłoszeniem; znaczenie wartości opisuje `ClosedTicketResponse`.
Outcome = Literal["blocked", "indexed", "dropped"]

# Werdykt bramki zamknięcia, w tych samych wartościach co w odpowiedzi `/gate/close`.
GateVerdict = Literal["pass", "block"]


class RuleHitItem(BaseModel):
    """
    Description:
    Jedna reguła filtra jakości, która odrzuciła kartę, i fragment, który ją uruchomił. Przy
    regule `not_useful` fragmentem jest uzasadnienie modelu z karty (`useful_reason`).
    """

    rule:     str = Field(examples=["not_useful"])
    evidence: str = Field(examples=["Wątek tylko potwierdza zamknięcie sprawy."])


class ClosedTicketResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /tickets/closed`: werdykt bramki zamknięcia i to, co stało się ze zgłoszeniem
    w korpusie.

    Pola werdyktu nazywają się jak w odpowiedzi `/gate/close`, więc helpdesk obsługuje werdykt
    jednym kodem: `overridable` jest zawsze `true` (zasada 10), a `rules_version` mówi, którą
    wersją reguł go wydano. `outcome` mówi, co zrobiono:

    | `outcome` | co się stało                                                            |
    |-----------|-------------------------------------------------------------------------|
    | `blocked` | bramka zablokowała; korpus i indeksy bez zmian, karty nie robiono       |
    | `indexed` | karta i wątek zapisane w korpusie, karta przyjęta przez filtr i w obu   |
    |           | indeksach                                                               |
    | `dropped` | karta i wątek zapisane w korpusie, ale filtr kartę odrzucił, więc       |
    |           | zgłoszenia nie ma w indeksach (`dropped_by` mówi dlaczego)              |

    `replaced` mówi, że karta zastąpiła wcześniejszą kartę tego zgłoszenia (ponowne zamknięcie).
    `useful_reason` to uzasadnienie modelu z karty, `null` przy blokadzie. `usage` i `log`
    obejmują oba grafy: najpierw przebieg bramki, potem karty.
    """

    ticket_id:     str               = Field(examples=["41002"])
    outcome:       Outcome           = Field(examples=["indexed"])
    replaced:      bool              = Field(examples=[False])
    verdict:       GateVerdict       = Field(examples=["pass"])
    reasons:       list[str]         = Field(default_factory=list, examples=[["Brak."]])
    hint:          str               = Field(default="", examples=[""])
    overridable:   bool              = Field(default=True, examples=[True])
    rules_version: int               = Field(examples=[1])
    useful_reason: str | None        = Field(default=None, examples=["Wątek podaje przyczynę."])
    dropped_by:    list[RuleHitItem] = Field(default_factory=list)
    usage:         UsageItem
    log:           list[LogItem]     = Field(default_factory=list)
