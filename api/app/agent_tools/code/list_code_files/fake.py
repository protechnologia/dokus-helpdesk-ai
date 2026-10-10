from collections.abc import Iterable

from app.agent_tools.code.fake_code import default_files
from app.agent_tools.code.list_code_files.base import (
    ROOT_DIR,
    ListCodeFilesToolBase,
    select_entries_and_build_result,
)
from app.agent_tools.code.list_code_files.errors import NoSuchCodeDirError
from app.agent_tools.code.list_code_files.models import ListCodeFilesQuery, ListCodeFilesResult


class FakeListCodeFilesTool(ListCodeFilesToolBase):
    """
    Description:
    Atrapa `list_code_files`: zamiast paczki na dysku zna ścieżki zmyślonych plików wspólnych
    dla atrap narzędzi kodu (`agent_tools/code/fake_code.py`). Odpowiada NA TO, o co pytano —
    spis nie ma „zawsze tego samego wyniku".

    Flow:
        1. Test tworzy ją z własnymi ścieżkami plików albo z zestawem wbudowanym.
        2. Każde `list_dir()` zapisuje zapytanie w `queries` i oddaje spis katalogu złożony ze
           znanych ścieżek; ścieżka pliku albo katalog, pod którym nic nie leży, kończy się
           `NoSuchCodeDirError`.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.

    Ścieżkę atrapa bierze dosłownie, bez ukośnika na końcu: nie rozwiązuje `..` i nie pilnuje
    granicy paczki, bo paczki nie ma. To sprawdza narzędzie właściwe na prawdziwym folderze.
    """

    def __init__(
        self,
        files: Iterable[str] | None = None,  # np. ["src/lib/Blad.php", "src/web/index.php"]
    ):
        """
        Description:
        Ustala ścieżki plików, które atrapa zna, i zakłada dziennik zapytań. Przyjmuje same
        ścieżki, więc można jej podać ten sam słownik plików co atrapie odczytu.

        Example args:
            files=None

        Example result:
            FakeListCodeFilesTool znająca ścieżki dwóch wbudowanych plików
        """
        self._files = sorted(files if files is not None else default_files())

        # Publiczne celowo: testy sprawdzają, które katalogi agent oglądał.
        self.queries: list[ListCodeFilesQuery] = []

    async def list_dir(
        self,
        query: ListCodeFilesQuery,  # np. ListCodeFilesQuery(path="src/lib", depth=1)
    ) -> ListCodeFilesResult:
        """
        Description:
        Zapisuje zapytanie i oddaje spis katalogu złożony ze znanych ścieżek plików.

        Example args:
            query=ListCodeFilesQuery(path="src/lib", depth=1)

        Example result:
            ListCodeFilesResult(path="src/lib", dir_info=CodeDirInfo(total_depth=3),
                                requested=RequestedDepth(depth=1),
                                returned=ReturnedDepth(depth=1, depth_cut_by_limit=False,
                                                       has_more_depth=True,
                                                       omitted_over_limit=0),
                                entries=[CodeDirEntry(path="src/lib/Urzad", kind="dir")])

        Raises:
            NoSuchCodeDirError: atrapa nie zna katalogu pod tą ścieżką
        """
        self.queries.append(query)

        asked = query.path or ROOT_DIR

        # --- katalog główny: wszystko, co atrapa zna; bez plików spis jest po prostu pusty ---
        if asked == ROOT_DIR:
            return select_entries_and_build_result(query, ROOT_DIR, self._files)

        path  = asked.rstrip("/")
        files = [file for file in self._files if file.startswith(f"{path}/")]

        # --- ścieżka znanego pliku: spis ma sens tylko dla katalogu ---
        if path in self._files:
            raise NoSuchCodeDirError(f"to plik, nie katalog: {asked}")

        # --- nic pod ścieżką: katalog istnieje tu tylko wtedy, gdy leży pod nim plik ---
        if not files:
            raise NoSuchCodeDirError(
                f"nie ma takiego pliku ani katalogu w kodzie aplikacji: {asked}"
            )

        return select_entries_and_build_result(query, path, files)
