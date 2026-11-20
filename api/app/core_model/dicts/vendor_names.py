from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core_util.repetition import words_of


class VendorNames(BaseModel):
    """
    Description:
    Nazwy firmy dostawcy tak, jak stoją w podpisie jej pracowników („TENSOFT Sp. z o.o.”).
    Po nich normalizer maili rozpoznaje, że wiadomość w kanale „Automat mailowy” napisał
    dostawca, a nie klient: role z bazy są w tym kanale błędne (p. 32).

    Plik `nazwy.json` pisze człowiek i leży obok `slownik.json` w katalogu słownika maili; skrypt
    słownika go nie rusza. Nazwę porównuje się słowami, bez wielkości liter i interpunkcji, więc
    „Tensoft sp. z o.o.” to ta sama nazwa. Nazwa razem z formą prawną jest pewniejsza niż sama
    marka: klient pisze „zgłaszam do Tensoftu”, a formę prawną ma zwykle tylko stopka.
    """

    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(min_length=1, examples=[["TENSOFT Sp. z o.o."]])

    @field_validator("names")
    @classmethod
    def _every_name_has_words(cls, names: list[str]) -> list[str]:   # np. ["TENSOFT Sp. z o.o."]
        """
        Description:
        Odrzuca nazwę bez ani jednego słowa: pasowałaby do każdej wiadomości, więc każdą
        uznałaby za wiadomość dostawcy.

        Example args:
            names=["TENSOFT Sp. z o.o."]

        Example result:
            ["TENSOFT Sp. z o.o."]

        Raises:
            ValueError: któraś nazwa nie ma słów (pusta, same odstępy albo interpunkcja)
        """
        for name in names:
            if not words_of(name):
                raise ValueError(f"nazwa dostawcy bez słów: {name!r}")

        return names
