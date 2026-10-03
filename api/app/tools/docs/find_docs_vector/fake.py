from collections.abc import Sequence

from app.tools.docs.fake_docs import default_sections
from app.tools.docs.find_docs_vector.base import FindDocsVectorToolBase
from app.tools.docs.find_docs_vector.models import (
    FindDocsVectorQuery,
    FindDocsVectorResult,
    FoundSection,
)


def default_found() -> list[FoundSection]:
    """
    Description:
    Wbudowany wynik atrapy: sekcja o uprawnieniu do kancelarii e-Doręczeń i — z niższym
    podobieństwem — jej dystraktor o skrzynce ePUAP. Ten sam temat w dwóch kanałach to sytuacja,
    w której agent ma przeczytać opis, zanim sięgnie po odczyt.

    Example args:
        (brak)

    Example result:
        [FoundSection(score=0.74, section=DocSection(…)), FoundSection(score=0.68, …)]
    """
    edoreczenia, epuap, _, _ = default_sections()

    found = [
        FoundSection(score=0.74, section=edoreczenia),
        FoundSection(score=0.68, section=epuap),
    ]

    return found


class FakeFindDocsVectorTool(FindDocsVectorToolBase):
    """
    Description:
    Atrapa `find_docs_vector`: zamiast kolekcji dokumentacji zwraca ustalony zestaw sekcji, zawsze
    ten sam, ze stałymi id. Ta sama rola co `FakeFindTicketsVectorTool`.

    Flow:
        1. Test tworzy ją z własnymi sekcjami albo z zestawem wbudowanym.
        2. Każde `find()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render()` i `run()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        found:                   Sequence[FoundSection] | None = None,  # np. [FoundSection(…)]
        dropped_below_threshold: int = 0,                               # np. 1
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            found=None
            dropped_below_threshold=0

        Example result:
            FakeFindDocsVectorTool zwracająca wbudowane dwie sekcje przy każdym wyszukaniu
        """
        self._result = FindDocsVectorResult(
            items                   = list(found) if found is not None else default_found(),
            dropped_below_threshold = dropped_below_threshold,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindDocsVectorQuery] = []

    async def find(
        self,
        query: FindDocsVectorQuery,  # np. FindDocsVectorQuery(text="uprawnienia kancelaria")
    ) -> FindDocsVectorResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            FindDocsVectorResult(items=[FoundSection(score=0.74, …), …], dropped_below_threshold=0)
        """
        self.queries.append(query)

        return self._result
