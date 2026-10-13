from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field

from app.core_model.code.code_symbol import CodeSymbol


class CodeSymbolMap(BaseModel):
    """
    Description:
    Mapa symboli paczki kodu aplikacji: dla każdego pliku PHP i JS lista definicji funkcji,
    metod i klas. Treść pliku `symbols.json`, który skrypt `scripts/build_code_symbols.py`
    zapisuje obok metryczki paczki.

    Do czego:
    Jedyne miejsce, z którego `api` zna granice funkcji: kodu samo nie rozbiera, bo parser
    jest tylko w zależnościach skryptów.

    W `files` są wyłącznie pliki z choć jedną definicją; ścieżki liczą się od `repo/`, jak
    w narzędziach kodu. Plik z `syntax_errors` parser odrzucił, więc w `files` go nie ma, choć
    definicje w nim są — to co innego niż plik bez definicji.
    """

    model_config = ConfigDict(extra="forbid")

    built_on:      Date                        = Field(examples=["2026-10-13"])
    syntax_errors: list[str]                   = Field(examples=[["src/lib/task/stary.php"]])
    files:         dict[str, list[CodeSymbol]]
