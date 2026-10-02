from pydantic import BaseModel, ConfigDict


class SearchDone(BaseModel):
    """
    Description:
    Argumenty `respond_search` — pusto z założenia. Wywołanie to sam sygnał, że agent skończył
    szukać. Wynikiem wyszukiwania są źródła z `cite()` (pole `sources` stanu) i zapytania, które
    agent wysłał (wywołania narzędzi w `messages`) — oba z przebiegu, nic z deklaracji modelu
    (zasada 9).
    """

    model_config = ConfigDict(extra="forbid")
