from collections.abc import Mapping

from app.agent_tools.code.fake_code import default_files
from app.agent_tools.code.read_code_file.base import (
    ReadCodeFileToolBase,
    select_lines_and_build_result,
)
from app.agent_tools.code.read_code_file.errors import NoSuchCodeFileError
from app.agent_tools.code.read_code_file.models import ReadCodeFileQuery, ReadCodeFileResult
from app.core_service.loader_code_package import split_lines


class FakeReadCodeFileTool(ReadCodeFileToolBase):
    """
    Description:
    Atrapa `read_code_file`: zamiast paczki na dysku zna zmyślone pliki wspólne dla atrap narzędzi
    kodu (`agent_tools/code/fake_code.py`). Odpowiada NA TO, o co pytano — odczyt nie ma „zawsze
    tego samego wyniku".

    Flow:
        1. Test tworzy ją z własnymi plikami albo z zestawem wbudowanym.
        2. Każde `read()` zapisuje zapytanie w `queries` i oddaje żądany zakres linii znanego
           pliku; nieznana ścieżka kończy się `NoSuchCodeFileError`, a początek za końcem pliku
           `StartOutOfFileError`.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.

    Ścieżkę atrapa bierze dosłownie: nie rozwiązuje `..` i nie pilnuje granicy paczki, bo paczki
    nie ma. To sprawdza narzędzie właściwe na prawdziwym folderze.
    """

    def __init__(
        self,
        files: Mapping[str, str] | None = None,  # np. {"src/lib/Blad.php": "<?php\\n…"}
    ):
        """
        Description:
        Ustala pliki, które atrapa zna, i zakłada dziennik zapytań.

        Example args:
            files=None

        Example result:
            FakeReadCodeFileTool znająca dwa wbudowane pliki
        """
        files = dict(files) if files is not None else default_files()

        # Linie dzielone tą samą funkcją co w czytniku paczki, więc numery znaczą to samo.
        self._lines = {path: split_lines(code) for path, code in files.items()}

        # Publiczne celowo: testy sprawdzają, które pliki i zakresy agent czytał.
        self.queries: list[ReadCodeFileQuery] = []

    async def read(
        self,
        query: ReadCodeFileQuery,  # np. ReadCodeFileQuery(path="…", from_line=7, to_line=9)
    ) -> ReadCodeFileResult:
        """
        Description:
        Zapisuje zapytanie i oddaje żądany zakres linii znanego pliku.

        Example args:
            query=ReadCodeFileQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                    from_line=7, to_line=9)

        Example result:
            ReadCodeFileResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                               file_info=CodeFileInfo(total_lines=14),
                               requested=RequestedLines(from_line=7, to_line=9),
                               returned=ReturnedLines(from_line=7, to_line=9, cut_by_limit=False,
                                                      end_of_file=False),
                               lines=[CodeLine(line=7, text="        $sekwencja = …"), …])

        Raises:
            NoSuchCodeFileError: atrapa nie zna pliku pod tą ścieżką
            StartOutOfFileError: odczyt zaczyna się za ostatnią linią pliku albo plik jest pusty
        """
        self.queries.append(query)

        if query.path not in self._lines:
            raise NoSuchCodeFileError(f"nie ma takiego pliku w kodzie aplikacji: {query.path}")

        return select_lines_and_build_result(query, query.path, self._lines[query.path])
