from pydantic import BaseModel, ConfigDict, Field


class PolishedText(BaseModel):
    """
    Description:
    Wynik „Popraw": ten sam sens co w notatkach wdrożeniowca, w poprawnej formie. Jedyny wynik
    grafu, który idzie do klienta jako tekst do wysłania — zawsze po akceptacji człowieka, nigdy
    w miejsce oryginału automatycznie (CLAUDE.md -> „Bramki jakości i asysta pisania").
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["Dzień dobry, przesyłki z e-Doręczeń…"])
