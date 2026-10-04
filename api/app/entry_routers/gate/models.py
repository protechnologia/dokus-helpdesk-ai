from typing import Literal

from pydantic import BaseModel, Field

from app.entry_routers.models import LogItem, UsageItem


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
    usage:         UsageItem
    log:           list[LogItem]            = Field(default_factory=list)


class GateReplyRequest(BaseModel):
    """
    Description:
    Wejście `POST /gate/reply`: wiadomość do klienta, którą wdrożeniowiec chce wysłać, i zgłoszenie,
    którego dotyczy (do logów).
    """

    ticket_id: str = Field(examples=["41002"])
    message:   str = Field(min_length=1, examples=["Dzień dobry, proszę podać hasło do skrzynki."])
