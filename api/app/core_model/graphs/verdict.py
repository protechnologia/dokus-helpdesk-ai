from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Verdict(BaseModel):
    """
    Description:
    Werdykt bramki jakości: przepuszcza czy blokuje, dlaczego, czego brakuje i co dopisać.

    Do czego:
    Jeden kształt dla bramki zamknięcia i bramki wysyłki — wołający pisze jedną obsługę odpowiedzi,
    a bramki różni zestaw reguł, nie kontrakt (CLAUDE.md -> „Warstwa API"). Dane, nie proza:
    helpdesk pokazuje `missing` jako listę we własnym UI. Wynik grafów `gate_close` i `gate_reply`.

    Blokada zawsze niesie uzasadnienie i wskazówkę (zasada 10) — inaczej to samo „nie", którego
    wdrożeniowcy nauczą się obchodzić na ślepo. Pilnuje tego walidacja, więc odpowiedź modelu bez
    nich wraca do poprawki jak każdy inny błąd formatu. Furtka (werdykt da się nadpisać) jest stała
    dla każdego werdyktu, więc należy do odpowiedzi API, nie do tego modelu.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "block"] = Field(examples=["block"])
    reasons: list[str]                = Field(default_factory=list, examples=[["Nie widać zmian."]])
    missing: list[str]                = Field(default_factory=list, examples=[["co zrobiono"]])
    hint:    str                      = Field(default="", examples=["Dopisz, co zmieniono."])

    @model_validator(mode="after")
    def check_block_is_explained(self) -> "Verdict":
        """
        Description:
        Odrzuca blokadę bez uzasadnienia albo bez wskazówki.

        Example args:
            (brak)

        Example result:
            Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz…")

        Raises:
            ValueError: `block` z pustym `reasons` albo pustym `hint`
        """
        if self.verdict == "block" and not (self.reasons and self.hint.strip()):
            raise ValueError("werdykt block musi nieść uzasadnienie (reasons) i wskazówkę (hint)")

        return self
