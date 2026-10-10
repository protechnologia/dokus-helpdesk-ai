"""
Description:
Prawdziwe narzędzie `list_code_files`: oddaje spis katalogu z paczki kodu aplikacji, do żądanej
głębokości. Nie woła embeddera, bazy ani LLM-a — tylko folder paczki.

    ścieżka katalogu → pliki pod nim → poziomy → tyle pełnych poziomów, ile mieści limit pozycji

Przed — zapytanie agenta bez argumentów, czyli dwa poziomy od katalogu głównego kodu:

    ListCodeFilesQuery()

Po — wynik `list_dir()` na paczce z aplikacji syntetycznej:

    ListCodeFilesResult(
        path      = ".",
        dir_info  = CodeDirInfo(total_depth=7),
        requested = RequestedDepth(depth=2),
        returned  = ReturnedDepth(depth=2, depth_cut_by_limit=False, has_more_depth=True,
                                  omitted_over_limit=0),
        entries   = [
            CodeDirEntry(path="src",        kind="dir"),
            CodeDirEntry(path="src/apps",   kind="dir"),
            CodeDirEntry(path="src/config", kind="dir"),
            CodeDirEntry(path="src/lib",    kind="dir"),
            CodeDirEntry(path="src/web",    kind="dir"),
        ],
    )

Co się dzieje po drodze:

1. Czytnik paczki sprawdza ścieżkę i oddaje ją w jednej postaci, względnej wobec kodu.
2. Ścieżka spoza paczki, plik albo brak katalogu kończy się `NoSuchCodeDirError`.
3. Czytnik oddaje ścieżki wszystkich plików pod katalogiem, na każdej głębokości.
4. Z nich powstają poziomy, a wynik bierze tyle pełnych, ile mieści
   `MAX_ENTRIES_PER_LISTING`; sygnały w wyniku mówią, co limit zabrał.

O czym pamiętać przy zmianach:

- Spis źródeł nie tworzy: mówi, co gdzie leży, nie co w plikach stoi.
- Pliki pod katalogiem są wyliczane w całości przy każdym wywołaniu, także gdy agent prosi
  o jeden poziom: głębokość całego katalogu da się policzyć tylko z kompletu. Spis od katalogu
  głównego paczki Dokusa (11 424 pliki) trwa 0,08 s.
- Spis pokazuje to, co jest w paczce, czyli pliki dobrane regułami skryptu paczki. Pliku,
  którego reguły nie wzięły, nie ma w spisie tak samo, jak nie da się go odczytać.
- Brak paczki pod skonfigurowaną ścieżką to `CodePackageConfigError`: nie wraca do modelu,
  zatrzymuje przebieg. Inaczej model dostawałby „nie ma takiego katalogu" na każdy spis.
"""

import logging

from app.agent_tools.code.list_code_files.base import (
    ROOT_DIR,
    ListCodeFilesToolBase,
    select_entries_and_build_result,
)
from app.agent_tools.code.list_code_files.errors import NoSuchCodeDirError
from app.agent_tools.code.list_code_files.models import ListCodeFilesQuery, ListCodeFilesResult
from app.core_service.loader_code_package import CodePackage, CodePathError

logger = logging.getLogger(__name__)


class ListCodeFilesTool(ListCodeFilesToolBase):
    """
    Description:
    `list_code_files` na prawdziwej paczce kodu: wylicza pliki pod katalogiem i oddaje spis do
    żądanej głębokości.

    Do czego:
    Spis katalogu kodu aplikacji w grafach `search`, `suggest_questions` i `suggest_solution`:
    gdy szukanie daje za dużo trafień albo model chce zobaczyć, co leży obok znalezionego
    pliku. Ścieżki ze spisu przyjmują odczyt pliku, szukanie i kolejny spis. Tylko do odczytu.

    Flow:
        1. `list_dir()` ustala ścieżkę katalogu w paczce i bierze ścieżki plików pod nim.
        2. `select_entries_and_build_result()` wybiera poziomy i składa wynik.
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
            ListCodeFilesTool gotowe do spisywania katalogów paczki
        """
        self._package = package

    async def list_dir(
        self,
        query: ListCodeFilesQuery,  # np. ListCodeFilesQuery(path="src/lib/Urzad/Wysylka")
    ) -> ListCodeFilesResult:
        """
        Description:
        Spisuje katalog z paczki do głębokości, o którą prosi zapytanie, najwyżej
        `MAX_ENTRIES_PER_LISTING` pozycji. Bez ścieżki spisuje katalog główny kodu.

        Example args:
            query=ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=1)

        Example result:
            ListCodeFilesResult(path="src/lib/Urzad/Wysylka",
                                dir_info=CodeDirInfo(total_depth=2),
                                requested=RequestedDepth(depth=1),
                                returned=ReturnedDepth(depth=1, depth_cut_by_limit=False, …),
                                entries=[CodeDirEntry(path="src/lib/Urzad/Wysylka/Edoreczenia",
                                                      kind="dir"), …])

        Raises:
            NoSuchCodeDirError: ścieżka nie wskazuje katalogu w paczce
            CodePackageConfigError: paczki nie ma pod skonfigurowaną ścieżką
        """
        asked = query.path or ROOT_DIR

        # --- katalog: ścieżka w jednej postaci i wszystkie pliki, które pod nim leżą ---
        try:
            path  = self._package.locate(asked, allow_dir=True)
            files = self._package.list_files(asked)
        except CodePathError as exc:
            # `from None`: wyjątek czytnika niczego tu nie dodaje, a komunikat idzie do modelu.
            raise NoSuchCodeDirError(str(exc)) from None

        result = select_entries_and_build_result(query, path, files)

        # Same liczby: ścieżkę podaje model, a wskazuje ona miejsce w kodzie klienta.
        logger.info(
            "list_code_files entries=%d depth=%d of=%d depth_cut_by_limit=%s omitted=%d",
            len(result.entries),
            result.returned.depth,
            result.dir_info.total_depth,
            result.returned.depth_cut_by_limit,
            result.returned.omitted_over_limit,
        )

        return result
