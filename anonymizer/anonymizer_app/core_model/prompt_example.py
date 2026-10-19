from typing import Any

from pydantic import BaseModel, ConfigDict


class PromptExample(BaseModel):
    """
    Description:
    Jeden przykład z promptu węzła (`examples.json` w katalogu węzła): tekst i odpowiedź, jaką
    model powinien na niego dać. Idzie do modelu jako wcześniejsza rozmowa, przed właściwym
    tekstem: tura użytkownika z tekstem i tura modelu z odpowiedzią. Przykłady są zmyślone
    i rozłączne z golden setem, inaczej pomiar byłby łatwiejszy, niż jest naprawdę.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text:   str             # np. "Od: Leszek Dudziak <{EMAIL}>\nDo: {EMAIL}…"
    answer: dict[str, Any]  # np. {"dane": [{"tekst": "Leszek", "rodzaj": "IMIĘ"}, …]}
