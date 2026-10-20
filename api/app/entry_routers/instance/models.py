from datetime import date as Date

from pydantic import BaseModel, Field

from app.core_model.instance.index_status import IndexName, IndexState, Material


class GenerationModelInfo(BaseModel):
    """
    Description:
    Model generujący instancji: dostawca i nazwa modelu. Przy atrapie (`fake`) nazwy nie ma,
    nawet gdy w `.env` stoi nazwa prawdziwego modelu — atrapa jej nie używa.
    """

    provider: str        = Field(examples=["openai"])
    name:     str | None = Field(examples=["gpt-6.1-sol"])


class IndexItem(BaseModel):
    """
    Description:
    Stan jednego indeksu materiału: `missing` (narzędzia na nim kończą się błędem konfiguracji),
    `empty` (oddają puste wyniki) albo `built`. `count` to punkty kolekcji, wiersze tabeli albo
    pliki paczki kodu; `null`, gdy indeksu nie ma.
    """

    material: Material   = Field(examples=["docs"])
    index:    IndexName  = Field(examples=["sections"])
    state:    IndexState = Field(examples=["empty"])
    count:    int | None = Field(examples=[0])


class CodePackageItem(BaseModel):
    """
    Description:
    Z której gałęzi i z którego dnia jest paczka kodu aplikacji. Odpowiedź z kodu opisuje tylko
    tę gałąź; `branch` to `null`, gdy paczka powstała z folderu, który nie jest kopią roboczą.
    """

    branch:   str | None = Field(examples=["/main/stage-gminy"])
    built_on: Date       = Field(examples=["2026-10-07"])


class InstanceResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /instance`: model generujący, stan pięciu indeksów (karty i wątki zgłoszeń,
    sekcje i fragmenty dokumentacji, paczka kodu) i gałąź paczki kodu — `null`, gdy paczki nie
    ma. Bez adresów usług i kluczy.
    """

    model:        GenerationModelInfo
    indexes:      list[IndexItem]
    code_package: CodePackageItem | None
