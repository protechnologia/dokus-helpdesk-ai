from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /health`. Nie mówi nic o konfiguracji — sondę osiągnie każdy, kto dosięgnie
    portu, więc nie może zdradzać, jakim silnikiem usługa działa.
    """

    status: str = Field(examples=["ok"])


class ErrorResponse(BaseModel):
    """
    Description:
    Jeden kształt błędu dla każdej obsłużonej awarii, ten sam co w `api` — wołającym jest właśnie
    `api`, więc jeden kształt to jedna obsługa po tamtej stronie. Nigdy nie cytuje tekstu, który
    przyszedł do anonimizacji.
    """

    detail:     str        = Field(examples=["Anonymization failed"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])


class AnonymizeRequest(BaseModel):
    """
    Description:
    Wejście `POST /anonymize`: jeden tekst — cały wątek zgłoszenia albo wiadomość, tak jak trafia
    do węzła `anonymize` w `api`.
    """

    text: str = Field(min_length=1, examples=["Jan Nowak zgłasza, że przesyłki nie przychodzą."])


class AnonymizeResponse(BaseModel):
    """
    Description:
    Wyjście `POST /anonymize`: tekst po anonimizacji i nazwa silnika, który go wytworzył. Nazwa
    silnika jest częścią kontraktu: `api` odmawia wyniku atrapy (`fake`), bo atrapa oddaje tekst
    bez zmian, a ten nie może trafić do prawdziwego modelu.
    """

    text:   str = Field(examples=["{IMIĘ} {NAZWISKO} zgłasza, że przesyłki nie przychodzą."])
    engine: str = Field(examples=["fake"])
