from app.agent_tools.errors import ToolCallError


class UnknownCodePathError(ToolCallError):
    """
    Description:
    Agent zawęził szukanie do ścieżki, która nie wskazuje pliku ani katalogu w kodzie aplikacji:
    wychodzi poza paczkę albo prowadzi donikąd.

    Błąd, a nie pusty wynik: „nic nie znaleziono" w katalogu, którego nie ma, wyglądałoby jak
    „takiego tekstu nie ma w kodzie". Komunikat wraca do modelu jako wynik narzędzia (stąd
    `ToolCallError`) i mówi, co jest nie tak ze ścieżką, w jej brzmieniu od modelu — bez
    położenia paczki na dysku.
    """

    def __init__(
        self,
        reason: str,  # np. "nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak"
    ):
        """
        Description:
        Przyjmuje gotowy opis problemu ze ścieżką, od czytnika paczki.

        Example args:
            reason="nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak"

        Example result:
            UnknownCodePathError("nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak")
        """
        super().__init__(reason)
