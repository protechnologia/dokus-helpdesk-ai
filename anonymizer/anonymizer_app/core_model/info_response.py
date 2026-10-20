from pydantic import BaseModel, Field


class InfoResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /info`: którym silnikiem usługa anonimizuje i z jakim modelem. Czyta ją `api`
    i podaje dalej w `GET /instance`, a front pokazuje ją na belce obok modelu generującego.

    Osobno od `/health`, które mówi tylko „ok": sondę wołają healthcheck i każdy, kto dosięgnie
    portu, a ta odpowiedź mówi o konfiguracji. Adresu serwera modelu ani klucza nie podaje.
    """

    engine: str        = Field(examples=["agent"])
    model:  str | None = Field(examples=["speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"])
