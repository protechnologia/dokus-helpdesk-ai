from app.agent_tools.errors import ToolCallError


class UnknownCodeFileError(ToolCallError):
    """
    Description:
    Agent zacytował ścieżkę, która nie wskazuje pliku w kodzie aplikacji: wychodzi poza paczkę,
    prowadzi do katalogu albo donikąd.

    Błąd, a nie potwierdzenie: cytowanie pliku, którego nie ma, stałoby na liście źródeł obok
    prawdziwych. Komunikat wraca do modelu jako wynik narzędzia (stąd `ToolCallError`) i mówi, co
    jest nie tak ze ścieżką, w jej brzmieniu od modelu — bez położenia paczki na dysku.
    """

    def __init__(
        self,
        reason: str,  # np. "nie ma takiego pliku w kodzie aplikacji: src/lib/Brak.php"
    ):
        """
        Description:
        Przyjmuje gotowy opis problemu ze ścieżką — od czytnika paczki albo od atrapy.

        Example args:
            reason="nie ma takiego pliku w kodzie aplikacji: src/lib/Brak.php"

        Example result:
            UnknownCodeFileError("nie ma takiego pliku w kodzie aplikacji: src/lib/Brak.php")
        """
        super().__init__(reason)


class LinesOutOfFileError(ToolCallError):
    """
    Description:
    Agent zacytował linie, których plik nie ma: fragment kończy się za ostatnią linią pliku.

    Błąd, a nie cytowanie przycięte do końca pliku: numery, które nie pasują do pliku, znaczą, że
    model cytuje z pamięci albo pomylił pliki. Komunikat podaje długość pliku, żeby mógł poprawić
    wywołanie.
    """

    def __init__(
        self,
        path:       str,  # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        to_line:    int,  # np. 31
        line_count: int,  # np. 27
    ):
        """
        Description:
        Zapamiętuje plik, żądany koniec fragmentu i długość pliku i składa z nich komunikat.

        Example args:
            path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
            to_line=31
            line_count=27

        Example result:
            LinesOutOfFileError("plik src/lib/Urzad/Numeracja/GeneratorNumeru.php ma 27 linii,
                                 a cytowanie sięga do linii 31")
        """
        self.path       = path
        self.to_line    = to_line
        self.line_count = line_count

        super().__init__(f"plik {path} ma {line_count} linii, a cytowanie sięga do linii {to_line}")
