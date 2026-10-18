from pydantic import BaseModel, Field


class AnonymizeResponse(BaseModel):
    """
    Description:
    Wyjście `POST /anonymize`: tekst po anonimizacji i nazwa silnika, który go wytworzył. Nazwa
    silnika jest częścią kontraktu: `api` odmawia wyniku atrapy (`fake`), bo atrapa oddaje tekst
    bez zmian, a ten nie może trafić do prawdziwego modelu.
    """

    text:   str = Field(examples=["{IMIĘ} {NAZWISKO} zgłasza, że przesyłki nie przychodzą."])
    engine: str = Field(examples=["fake"])
