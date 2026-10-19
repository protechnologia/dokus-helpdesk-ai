from pydantic import BaseModel, ConfigDict, Field


class LogEntry(BaseModel):
    """
    Description:
    Jeden wpis przebiegu grafu anonimizacji: który węzeł co zrobił. Silnik zapisuje wpisy do logu
    usługi po każdym tekście, więc kolejne kroki anonimizacji widać bez zewnętrznego tracingu.

    `message` niesie wyłącznie nazwy rodzajów i liczby, nigdy tekstu ani fragmentów: wejściem
    usługi jest surowe zgłoszenie, a log nie może go zapisać na żadnym poziomie.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node:    str = Field(min_length=1, examples=["find_persons"])
    message: str = Field(min_length=1, examples=["7 fragmentów → 19 miejsc"])
