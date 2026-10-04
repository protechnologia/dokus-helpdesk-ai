from pydantic import BaseModel, Field

from app.entry_routers.models import UsageItem


class PolishRequest(BaseModel):
    """
    Description:
    Wejście `POST /polish`: notatki wdrożeniowca do przepisania i zgłoszenie, którego dotyczą
    (do logów).
    """

    ticket_id: str = Field(examples=["41002"])
    text:      str = Field(min_length=1, examples=["przesylki juz ida, kolejka stala"])


class PolishResponse(BaseModel):
    """
    Description:
    Odpowiedź `POST /polish`: ten sam sens w poprawnej formie — zawsze do akceptacji człowieka,
    nigdy w miejsce oryginału automatycznie.
    """

    text:  str = Field(examples=["Dzień dobry, przesyłki z e-Doręczeń już docierają…"])
    usage: UsageItem
