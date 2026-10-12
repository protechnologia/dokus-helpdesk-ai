from collections.abc import Mapping

from app.agent_tools.code.fake_code import default_files
from app.agent_tools.code.quote_code.base import QuoteCodeToolBase, check_lines_and_build_result
from app.agent_tools.code.quote_code.errors import UnknownCodeFileError
from app.agent_tools.code.quote_code.models import QuoteCodeQuery, QuoteCodeResult
from app.core_service.loader_code_package import split_lines


class FakeQuoteCodeTool(QuoteCodeToolBase):
    """
    Description:
    Atrapa `quote_code`: zamiast paczki na dysku zna zmyślone pliki wspólne dla atrap narzędzi
    kodu (`agent_tools/code/fake_code.py`). Odpowiada NA TO, o co pytano — cytowanie nie ma
    „zawsze tego samego wyniku".

    Flow:
        1. Test tworzy ją z własnymi plikami albo z zestawem wbudowanym.
        2. Każde `search()` zapisuje zapytanie w `queries` i oddaje potwierdzenie cytowania;
           nieznana ścieżka kończy się `UnknownCodeFileError`, a linie spoza pliku
           `LinesOutOfFileError`.
        3. `render_for_model()` i `cite()` pochodzą z klasy wspólnej z prawdziwym narzędziem.

    Ścieżkę atrapa bierze dosłownie: nie rozwiązuje `..` i nie pilnuje granicy paczki, bo paczki
    nie ma. To sprawdza narzędzie właściwe na prawdziwym folderze.
    """

    def __init__(
        self,
        files:  Mapping[str, str] | None = None,  # np. {"src/lib/Blad.php": "<?php\\n…"}
        branch: str | None               = None,  # np. "/main/stage-gminy"; brak: paczka bez gałęzi
    ):
        """
        Description:
        Ustala pliki, które atrapa zna, i gałąź zmyślonej paczki, i zakłada dziennik zapytań.
        Bez gałęzi tytuł źródła nie ma dopisku, jak na paczce z aplikacji syntetycznej.

        Example args:
            files=None
            branch=None

        Example result:
            FakeQuoteCodeTool znająca dwa wbudowane pliki, bez gałęzi
        """
        files = dict(files) if files is not None else default_files()

        self._branch = branch

        # Linie liczone tą samą funkcją co w czytniku paczki, więc numery znaczą to samo.
        self._line_counts = {path: len(split_lines(code)) for path, code in files.items()}

        # Publiczne celowo: testy sprawdzają, co i w jakiej roli agent zacytował.
        self.queries: list[QuoteCodeQuery] = []

    async def search(
        self,
        query: QuoteCodeQuery,  # np. QuoteCodeQuery(path="…", from_line=8, to_line=10, …)
    ) -> QuoteCodeResult:
        """
        Description:
        Zapisuje zapytanie i oddaje potwierdzenie cytowania fragmentu znanego pliku.

        Example args:
            query=QuoteCodeQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                 from_line=8, to_line=10, role="cause")

        Example result:
            QuoteCodeResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", from_line=8,
                            to_line=10, role="cause")

        Raises:
            UnknownCodeFileError: atrapa nie zna pliku pod tą ścieżką
            LinesOutOfFileError: fragment kończy się za ostatnią linią pliku
        """
        self.queries.append(query)

        if query.path not in self._line_counts:
            raise UnknownCodeFileError(f"nie ma takiego pliku w kodzie aplikacji: {query.path}")

        quote = check_lines_and_build_result(
            query      = query,
            path       = query.path,
            line_count = self._line_counts[query.path],
            branch     = self._branch,
        )

        return quote
