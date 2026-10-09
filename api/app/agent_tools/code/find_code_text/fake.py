from collections.abc import Sequence

from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH, default_files
from app.agent_tools.code.find_code_text.base import FindCodeTextToolBase, shorten_line
from app.agent_tools.code.find_code_text.models import (
    FindCodeTextQuery,
    FindCodeTextResult,
    MatchedLine,
)
from app.agent_tools.models import MatchKind
from app.core_service.loader_code_package import split_lines


def matched_line_of_fake_file(
    path:       str,        # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    line:       int,        # np. 9 — numer linii, liczony od 1
    matched_by: MatchKind,  # np. "exact"
) -> MatchedLine:
    """
    Description:
    Składa trafienie z linii zmyślonego pliku atrap (`agent_tools/code/fake_code.py`): treść
    bierze z pliku i przycina tak samo jak narzędzie właściwe, więc ścieżka, numer i treść
    zgadzają się z tym, co o tym pliku wiedzą atrapy pozostałych narzędzi kodu.

    Example args:
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        line=9
        matched_by="exact"

    Example result:
        MatchedLine(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", line=9,
                    matched_by="exact",
                    text="throw new BrakSekwencjiException('Brak sekwencji numeracji dla roku '…")
    """
    lines   = split_lines(default_files()[path])
    matched = MatchedLine(
        path       = path,
        line       = line,
        matched_by = matched_by,
        text       = shorten_line(lines[line - 1]),
    )

    return matched


def default_matched() -> list[MatchedLine]:
    """
    Description:
    Wbudowany wynik atrapy: dwie linie z dwóch zmyślonych plików. Pierwsza to miejsce, w którym
    powstaje komunikat o braku sekwencji numeracji — przyczyna; druga to ogólny komunikat obsługi
    błędów w przeglądarce — miejsce, które pasuje do słów, ale sprawy nie tłumaczy.

    Example args:
        (brak)

    Example result:
        [MatchedLine(path="src/lib/Urzad/Numeracja/GeneratorNumeru.php", line=9, …),
         MatchedLine(path="src/web/js/_global/bledy.js", line=7, …)]
    """
    matched = [
        matched_line_of_fake_file(GENERATOR_PATH, line=9, matched_by="exact"),
        matched_line_of_fake_file(ERRORS_PATH,    line=7, matched_by="words"),
    ]

    return matched


class FakeFindCodeTextTool(FindCodeTextToolBase):
    """
    Description:
    Atrapa `find_code_text`: zamiast ripgrepa zwraca ustalone linie, zawsze te same. Ta sama rola
    co `FakeFindTicketsTextTool`.

    Flow:
        1. Test tworzy ją z własnymi liniami albo z zestawem wbudowanym; `omitted_over_limit`
           pozwala odtworzyć wynik „zapytanie zbyt ogólne", a pusta lista — „nie ma takiego
           tekstu w kodzie".
        2. Każde `find()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `run()` pochodzi z klasy wspólnej z prawdziwym narzędziem.

    Ścieżki zawężenia atrapa nie sprawdza, bo paczki nie ma. To sprawdza narzędzie właściwe na
    prawdziwym folderze.
    """

    def __init__(
        self,
        lines:              Sequence[MatchedLine] | None = None,  # np. [MatchedLine(…)]
        omitted_over_limit: int = 0,                              # np. 493
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            lines=None
            omitted_over_limit=0

        Example result:
            FakeFindCodeTextTool zwracająca wbudowane dwie linie przy każdym szukaniu
        """
        self._result = FindCodeTextResult(
            lines              = list(lines) if lines is not None else default_matched(),
            omitted_over_limit = omitted_over_limit,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindCodeTextQuery] = []

    async def find(
        self,
        query: FindCodeTextQuery,  # np. FindCodeTextQuery(exact="Brak sekwencji numeracji")
    ) -> FindCodeTextResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindCodeTextQuery(exact="Brak sekwencji numeracji")

        Example result:
            FindCodeTextResult(lines=[MatchedLine(path="src/lib/…/GeneratorNumeru.php", line=9,
                                                  matched_by="exact", text="throw new …"), …],
                               omitted_over_limit=0)
        """
        self.queries.append(query)

        return self._result
