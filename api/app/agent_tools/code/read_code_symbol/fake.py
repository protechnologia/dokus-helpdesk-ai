from collections.abc import Mapping

from app.agent_tools.code.fake_code import default_files, default_symbol_map
from app.agent_tools.code.read_code_symbol.base import (
    ReadCodeSymbolToolBase,
    find_symbol_and_build_result,
)
from app.agent_tools.code.read_code_symbol.errors import UnknownSymbolPathError
from app.agent_tools.code.read_code_symbol.models import ReadCodeSymbolQuery, ReadCodeSymbolResult
from app.core_model.code.code_symbol_map import CodeSymbolMap
from app.core_service.loader_code_package import split_lines
from app.core_util.path import is_path_under


class FakeReadCodeSymbolTool(ReadCodeSymbolToolBase):
    """
    Description:
    Atrapa `read_code_symbol`: zamiast paczki na dysku zna zmyślone pliki i ich mapę symboli,
    wspólne dla atrap narzędzi kodu (`agent_tools/code/fake_code.py`). Odpowiada NA TO, o co
    pytano — odczyt nie ma „zawsze tego samego wyniku".

    Flow:
        1. Test tworzy ją z własnymi plikami i mapą albo z zestawem wbudowanym.
        2. Każde `read()` zapisuje zapytanie w `queries` i oddaje definicję o podanej nazwie:
           jedną z liniami albo kilka jako kandydatów; brak definicji kończy się
           `NoSuchSymbolError`, a ścieżka, pod którą atrapa nie zna żadnego pliku,
           `UnknownSymbolPathError`.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.

    Ścieżkę atrapa bierze dosłownie: nie rozwiązuje `..` i nie pilnuje granicy paczki, bo paczki
    nie ma. To sprawdza narzędzie właściwe na prawdziwym folderze.
    """

    def __init__(
        self,
        files:      Mapping[str, str] | None = None,  # np. {"src/lib/Blad.php": "<?php\\n…"}
        symbol_map: CodeSymbolMap | None     = None,  # mapa symboli tych plików
    ):
        """
        Description:
        Ustala pliki i mapę symboli, które atrapa zna, i zakłada dziennik zapytań. Własne pliki
        podaje się razem z własną mapą, bo atrapa kodu nie rozbiera; własne pliki bez mapy to
        pliki bez żadnej definicji.

        Example args:
            files=None
            symbol_map=None

        Example result:
            FakeReadCodeSymbolTool znająca klasę `GeneratorNumeru` i jej metodę `nastepnyNumer`
        """
        # --- mapa: podana, wbudowana do wbudowanych plików albo pusta do własnych ---
        if symbol_map is None:
            symbol_map = default_symbol_map()
            if files is not None:
                symbol_map = symbol_map.model_copy(update={"files": {}})

        files = dict(files) if files is not None else default_files()

        # Linie dzielone tą samą funkcją co w czytniku paczki, więc numery znaczą to samo.
        self._lines      = {path: split_lines(code) for path, code in files.items()}
        self._symbol_map = symbol_map

        # Publiczne celowo: testy sprawdzają, o które definicje agent prosił.
        self.queries: list[ReadCodeSymbolQuery] = []

    async def read(
        self,
        query: ReadCodeSymbolQuery,  # np. ReadCodeSymbolQuery(name="nastepnyNumer")
    ) -> ReadCodeSymbolResult:
        """
        Description:
        Zapisuje zapytanie i oddaje definicję o podanej nazwie ze znanych plików.

        Example args:
            query=ReadCodeSymbolQuery(name="nastepnyNumer")

        Example result:
            ReadCodeSymbolResult(requested=RequestedSymbol(name="nastepnyNumer", path=None),
                                 symbol=SymbolDefinition(path="src/…/GeneratorNumeru.php", …),
                                 returned=ReturnedSymbolLines(from_line=5, to_line=13,
                                                              cut_by_limit=False),
                                 lines=[SymbolLine(line=5, text="    public function …"), …])

        Raises:
            UnknownSymbolPathError: atrapa nie zna żadnego pliku pod tą ścieżką
            NoSuchSymbolError: pod ścieżką nie ma definicji o tej nazwie
        """
        self.queries.append(query)

        if query.path and not any(is_path_under(path, query.path) for path in self._lines):
            raise UnknownSymbolPathError(
                f"nie ma takiego pliku ani katalogu w kodzie aplikacji: {query.path}"
            )

        result = find_symbol_and_build_result(
            query      = query,
            inside     = query.path,
            symbol_map = self._symbol_map,
            read_lines = self._lines.__getitem__,
        )

        return result
