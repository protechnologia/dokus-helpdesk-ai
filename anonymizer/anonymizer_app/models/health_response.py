from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /health`. Nie mówi nic o konfiguracji — sondę osiągnie każdy, kto dosięgnie
    portu, więc nie może zdradzać, jakim silnikiem usługa działa.
    """

    status: str = Field(examples=["ok"])
