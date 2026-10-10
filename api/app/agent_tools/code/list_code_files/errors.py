from app.agent_tools.errors import ToolCallError


class NoSuchCodeDirError(ToolCallError):
    """
    Description:
    Agent chciał spisu ścieżki, która nie wskazuje katalogu w kodzie aplikacji: wychodzi poza
    paczkę, prowadzi do pliku albo donikąd.

    Komunikat wraca do modelu jako wynik narzędzia (stąd `ToolCallError`) i mówi, co jest nie
    tak ze ścieżką, w jej brzmieniu od modelu — bez położenia paczki na dysku.
    """

    def __init__(
        self,
        reason: str,  # np. "nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak"
    ):
        """
        Description:
        Przyjmuje gotowy opis problemu ze ścieżką — od czytnika paczki albo od atrapy.

        Example args:
            reason="to plik, nie katalog: src/web/index.php"

        Example result:
            NoSuchCodeDirError("to plik, nie katalog: src/web/index.php")
        """
        super().__init__(reason)
