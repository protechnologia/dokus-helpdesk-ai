from app.agent_tools.errors import ToolCallError


class NoSuchCodeFileError(ToolCallError):
    """
    Description:
    Agent chciał przeczytać ścieżkę, która nie wskazuje pliku w kodzie aplikacji: wychodzi poza
    paczkę, prowadzi do katalogu albo donikąd.

    Komunikat wraca do modelu jako wynik narzędzia (stąd `ToolCallError`) i mówi, co jest nie
    tak ze ścieżką, w jej brzmieniu od modelu — bez położenia paczki na dysku.
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
            NoSuchCodeFileError("nie ma takiego pliku w kodzie aplikacji: src/lib/Brak.php")
        """
        super().__init__(reason)


class StartOutOfFileError(ToolCallError):
    """
    Description:
    Agent chciał czytać od linii, której plik nie ma: odczyt zaczyna się za ostatnią linią pliku
    albo plik jest pusty.

    Błąd, a nie pusty wynik: wynik bez linii wyglądałby jak przeczytany fragment, w którym nic
    nie ma. Komunikat podaje długość pliku, żeby model mógł poprawić wywołanie. Koniec zakresu
    za końcem pliku błędem nie jest — narzędzie oddaje wtedy linie do końca pliku.
    """

    def __init__(
        self,
        path:       str,  # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        from_line:  int,  # np. 31
        line_count: int,  # np. 27
    ):
        """
        Description:
        Zapamiętuje plik, żądany początek odczytu i długość pliku i składa z nich komunikat.

        Example args:
            path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
            from_line=31
            line_count=27

        Example result:
            StartOutOfFileError("plik src/lib/Urzad/Numeracja/GeneratorNumeru.php ma 27 linii,
                                 a odczyt zaczyna się od linii 31")
        """
        self.path       = path
        self.from_line  = from_line
        self.line_count = line_count

        # --- plik bez linii: nie ma w nim czego czytać, od którejkolwiek linii by zacząć ---
        if line_count == 0:
            message = f"plik {path} jest pusty"
        # --- plik krótszy niż początek odczytu ---
        else:
            message = (
                f"plik {path} ma {line_count} linii, a odczyt zaczyna się od linii {from_line}"
            )

        super().__init__(message)
