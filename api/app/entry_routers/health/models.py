from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Description:
    Odpowiedź `GET /health`. Celowo nic o konfiguracji — sonda żywotności jest osiągalna dla
    każdego, kto dosięgnie usługi, więc nie może zdradzać dostawców, adresów ani modeli.
    """

    status: str = Field(examples=["ok"])
