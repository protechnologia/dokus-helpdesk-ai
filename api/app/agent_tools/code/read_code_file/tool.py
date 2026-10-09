"""
Description:
Prawdziwe narzędzie `read_code_file`: oddaje plik albo zakres linii z paczki kodu aplikacji,
z numerami linii. Nie woła embeddera, bazy ani LLM-a — tylko folder paczki.

    ścieżka i zakres linii → plik w paczce → linie pliku → żądany zakres, najwyżej limit linii

Przed — zapytanie agenta (plik ma 441 linii):

    ReadCodeFileQuery(path="src/apps/frontend/modules/sprawy/actions/actions.class.php")

Po — wynik `read()`:

    ReadCodeFileResult(
        path      = "src/apps/frontend/modules/sprawy/actions/actions.class.php",
        file_info = CodeFileInfo(total_lines=441),
        requested = RequestedLines(from_line=1, to_line=None),
        returned  = ReturnedLines(from_line=1, to_line=300, cut_by_limit=True, end_of_file=False),
        lines     = [CodeLine(line=1, text="<?php"), …],  # 300 pozycji
    )

Co się dzieje po drodze:

1. Czytnik paczki sprawdza ścieżkę i oddaje ją w jednej postaci, względnej wobec kodu.
2. Ścieżka spoza paczki, katalog albo brak pliku kończy się `NoSuchCodeFileError`.
3. Odczyt od linii, której plik nie ma, kończy się `StartOutOfFileError`.
4. Z linii pliku wybierany jest żądany zakres, najwyżej `MAX_LINES_PER_READ` linii; wynik mówi,
   który zakres oddano i czy odczyt urwał limit, czy skończył się plik.

O czym pamiętać przy zmianach:

- Odczyt źródeł nie tworzy. Plik zawsze da się przeczytać, więc przy odczycie tworzącym źródła
  wariant wymagający źródeł prawie nigdy nie powiedziałby „nie mam z czego zaproponować".
- Plik jest czytany w całości przy każdym wywołaniu, także gdy agent prosi o kilka linii:
  numery linii da się policzyć tylko od początku pliku.
- Długość zakresu sprawdza się tutaj, nie w modelu zapytania: za długi zakres nie jest błędem,
  tylko odczytem urwanym limitem.
- Brak paczki pod skonfigurowaną ścieżką to `CodePackageConfigError`: nie wraca do modelu,
  zatrzymuje przebieg. Inaczej model dostawałby „nie ma takiego pliku" na każdy odczyt.
"""

import logging

from app.agent_tools.code.read_code_file.base import (
    ReadCodeFileToolBase,
    select_lines_and_build_result,
)
from app.agent_tools.code.read_code_file.errors import NoSuchCodeFileError
from app.agent_tools.code.read_code_file.models import ReadCodeFileQuery, ReadCodeFileResult
from app.core_service.loader_code_package import CodePackage, CodePathError

logger = logging.getLogger(__name__)


class ReadCodeFileTool(ReadCodeFileToolBase):
    """
    Description:
    `read_code_file` na prawdziwej paczce kodu: czyta plik z dysku i oddaje żądany zakres linii.

    Do czego:
    Odczyt kodu aplikacji w grafach `search`, `suggest_questions` i `suggest_solution` — drugi
    krok po szukaniu (`find_code_text`): linia znaleziona szukaniem mówi, gdzie tekst stoi,
    a odczyt pokazuje, w jakim warunku kod do niej dochodzi. Tylko do odczytu.

    Flow:
        1. `read()` ustala ścieżkę w paczce i czyta linie pliku.
        2. `select_lines_and_build_result()` wybiera zakres i składa wynik.
        3. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        package: CodePackage,  # np. CodePackage(Path("/code/data/unsafe/code"))
    ):
        """
        Description:
        Spina narzędzie z paczką kodu. Paczka jest wstrzykiwana, nie budowana tutaj.

        Example args:
            package=CodePackage(Path("/code/data/unsafe/code"))

        Example result:
            ReadCodeFileTool gotowe do czytania plików z paczki
        """
        self._package = package

    async def read(
        self,
        query: ReadCodeFileQuery,  # np. ReadCodeFileQuery(path="…", from_line=12, to_line=40)
    ) -> ReadCodeFileResult:
        """
        Description:
        Odczytuje z pliku w paczce zakres linii, o który prosi zapytanie, najwyżej
        `MAX_LINES_PER_READ` linii.

        Example args:
            query=ReadCodeFileQuery(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                                    from_line=12, to_line=40)

        Example result:
            ReadCodeFileResult(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php",
                               file_info=CodeFileInfo(total_lines=27),
                               requested=RequestedLines(from_line=12, to_line=40),
                               returned=ReturnedLines(from_line=12, to_line=27, …),
                               lines=[CodeLine(line=12, text="…"), …])

        Raises:
            NoSuchCodeFileError: ścieżka nie wskazuje pliku w paczce
            StartOutOfFileError: odczyt zaczyna się za ostatnią linią pliku albo plik jest pusty
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
        """
        # --- plik: ścieżka w jednej postaci i wszystkie linie ---
        try:
            path  = self._package.locate(query.path)
            lines = self._package.read_lines(path)
        except CodePathError as exc:
            # `from None`: wyjątek czytnika niczego tu nie dodaje, a komunikat idzie do modelu.
            raise NoSuchCodeFileError(str(exc)) from None

        result = select_lines_and_build_result(query, path, lines)

        # Same liczby: ścieżkę podaje model, a wskazuje ona miejsce w kodzie klienta.
        logger.info(
            "read_code_file lines=%d of=%d cut_by_limit=%s end_of_file=%s",
            len(result.lines),
            result.file_info.total_lines,
            result.returned.cut_by_limit,
            result.returned.end_of_file,
        )

        return result
