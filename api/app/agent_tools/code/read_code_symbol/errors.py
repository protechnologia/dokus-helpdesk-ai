from app.agent_tools.errors import ToolCallError


class UnknownSymbolPathError(ToolCallError):
    """
    Description:
    Agent zawęził odczyt symbolu do ścieżki, która nie wskazuje pliku ani katalogu w kodzie
    aplikacji: wychodzi poza paczkę albo prowadzi donikąd.

    Błąd, a nie „nie ma takiej definicji": brak definicji w katalogu, którego nie ma,
    wyglądałby jak brak definicji w kodzie. Komunikat wraca do modelu jako wynik narzędzia
    (stąd `ToolCallError`) i mówi, co jest nie tak ze ścieżką, w jej brzmieniu od modelu.
    """

    def __init__(
        self,
        reason: str,  # np. "nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak"
    ):
        """
        Description:
        Przyjmuje gotowy opis problemu ze ścieżką — od czytnika paczki albo od atrapy.

        Example args:
            reason="nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak"

        Example result:
            UnknownSymbolPathError("nie ma takiego pliku ani katalogu w kodzie aplikacji: src/brak")
        """
        super().__init__(reason)


class NoSuchSymbolError(ToolCallError):
    """
    Description:
    Do nazwy, o którą prosił agent, nie pasuje żadna definicja pod wskazaną ścieżką. Komunikat
    mówi, co zrobić dalej, zależnie od tego, co mapa symboli wie o tej nazwie:

    | co wie mapa                                          | co mówi komunikat                   |
    |------------------------------------------------------|-------------------------------------|
    | plik ze ścieżki parser odrzucił (błąd składni)       | czytać plik odczytem pliku          |
    | definicje są, ale poza wskazaną ścieżką              | poszerzyć `path` albo go pominąć    |
    | klasa nie ma takiej metody, ale sama nazwa jest      | podać samą nazwę i zawęzić `path`   |
    | takiej nazwy nie ma w kodzie wcale                   | poszukać jej szukaniem w kodzie     |

    Błąd, a nie pusty wynik: wynik bez linii wyglądałby jak przeczytana funkcja, w której nic
    nie ma.
    """

    def __init__(
        self,
        name:         str,         # np. "sprawyActions::executeResetuj"
        path:         str | None,  # np. "src/apps/frontend/modules/sprawy"; None: cały kod
        outside:      int,         # ile definicji pasuje do nazwy poza wskazaną ścieżką
        bare_name:    str | None,  # np. "executeResetuj"; None: nazwa podana bez miejsca
        bare_count:   int,         # ile definicji ma samą nazwę, w całym kodzie
        syntax_error: bool,        # ścieżka wskazuje plik, którego parser nie rozebrał
    ):
        """
        Description:
        Zapamiętuje, czego szukano i co mapa wie o tej nazwie, i składa z tego komunikat.

        Example args:
            name="executeResetuj"
            path="src/apps/frontend/modules/sprawy/actions/actions.class.php"
            outside=3
            bare_name=None
            bare_count=0
            syntax_error=False

        Example result:
            NoSuchSymbolError("pod ścieżką src/…/actions.class.php nie ma definicji o nazwie
                               executeResetuj; liczba definicji o tej nazwie poza tą ścieżką: 3
                               — poszerz `path`, na przykład do katalogu, albo go pomiń")
        """
        self.name    = name
        self.path    = path
        self.outside = outside

        where = f"pod ścieżką {path}" if path else "w kodzie aplikacji"

        # --- plik odrzucony przez parser: jego funkcje są w kodzie, ale nie w mapie ---
        if syntax_error:
            message = (
                f"plik {path} nie ma definicji w mapie symboli, bo parser zgłosił w nim błąd "
                f"składni — przeczytaj go narzędziem `read_code_file`"
            )
        # --- definicje są, ale gdzie indziej: typowo metoda w klasie bazowej obok ---
        elif outside > 0:
            message = (
                f"{where} nie ma definicji o nazwie {name}; liczba definicji o tej nazwie poza "
                f"tą ścieżką: {outside} — poszerz `path`, na przykład do katalogu, albo go pomiń"
            )
        # --- nazwa z miejscem nie pasuje, ale sama nazwa jest: metoda innej klasy ---
        elif bare_name is not None and bare_count > 0:
            message = (
                f"{where} nie ma definicji {name}; liczba definicji o samej nazwie {bare_name} "
                f"w całym kodzie: {bare_count} — podaj samą nazwę, a `path` zawęź do pliku albo "
                f"katalogu"
            )
        # --- nazwy nie ma w kodzie wcale ---
        else:
            message = (
                f"w kodzie aplikacji nie ma definicji funkcji, metody ani klasy o nazwie {name}: "
                f"nazwa może pochodzić z biblioteki albo powstawać w trakcie działania — "
                f"poszukaj jej narzędziem `find_code_text`"
            )

        super().__init__(message)
