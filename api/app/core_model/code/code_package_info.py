from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class CodePackageInfo(BaseModel):
    """
    Description:
    Z której wersji kodu aplikacji powstała paczka: gałąź repozytorium i dzień budowy. Obie
    wartości pochodzą z metryczki paczki (`manifest.json`), którą zapisuje skrypt paczki,
    a czyta `CodeDescription` z `core_service/loader_code_description.py`.

    Do czego:
    Odpowiedź z kodu opisuje tylko tę gałąź, z której zbudowano paczkę, a klienci mają własne
    gałęzie obok głównej. Dlatego gałąź dostaje model (w wyniku `describe_code` i w
    potwierdzeniu cytowania) i człowiek (w tytule źródła z kodu, który składa `quote_code`).

    Gałęzi może nie być: skrypt czyta ją z pliku kopii roboczej, a folder bez tego pliku — jak
    źródło aplikacji syntetycznej — daje metryczkę bez gałęzi. Pole jest wymagane, żeby brak
    był zapisany wprost, a nie wynikał z pominięcia.
    """

    model_config = ConfigDict(extra="forbid")

    branch:   str | None = Field(min_length=1, examples=["/main/stage-gminy"])
    built_on: Date       = Field(examples=["2026-10-07"])
