from collections.abc import Sequence

from app.tools.fake_docs import default_sections
from app.tools.find_docs_text.base import FindDocsTextToolBase
from app.tools.find_docs_text.models import FindDocsTextQuery, FindDocsTextResult, MatchedSection


def default_matched() -> list[MatchedSection]:
    """
    Description:
    Wbudowany wynik atrapy: sekcja znaleziona po dosłownym komunikacie z ekranu i sekcja
    znaleziona po słowach kluczowych — po jednej na każdą drogę dopasowania.

    Example args:
        (brak)

    Example result:
        [MatchedSection(matched_by="exact", snippet="Komunikat „Nie udało się…", …), …]
    """
    edoreczenia, _, _, brak_serwera = default_sections()

    matched = [
        MatchedSection(
            matched_by = "exact",
            snippet    = "Komunikat „Nie udało się skomunikować z serwerem” przy podpisie…",
            section    = brak_serwera,
        ),
        MatchedSection(
            matched_by = "words",
            snippet    = "Uprawnienie do kancelarii e-Doręczeń nadaje administrator…",
            section    = edoreczenia,
        ),
    ]

    return matched


class FakeFindDocsTextTool(FindDocsTextToolBase):
    """
    Description:
    Atrapa `find_docs_text`: zamiast Postgresa zwraca ustalony zestaw sekcji, zawsze ten sam, ze
    stałymi id. Ta sama rola co `FakeFindTicketsVectorTool`.

    Flow:
        1. Test tworzy ją z własnymi sekcjami albo z zestawem wbudowanym.
        2. Każde `find()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render()` i `run()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        matched:            Sequence[MatchedSection] | None = None,  # np. [MatchedSection(…)]
        omitted_over_limit: int = 0,                                 # np. 12
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            matched=None
            omitted_over_limit=0

        Example result:
            FakeFindDocsTextTool zwracająca wbudowane dwie sekcje przy każdym wyszukaniu
        """
        self._result = FindDocsTextResult(
            items              = list(matched) if matched is not None else default_matched(),
            omitted_over_limit = omitted_over_limit,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindDocsTextQuery] = []

    async def find(
        self,
        query: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> FindDocsTextResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindDocsTextQuery(exact=["Nie udało się skomunikować z serwerem"])

        Example result:
            FindDocsTextResult(items=[MatchedSection(matched_by="exact", …), …],
                               omitted_over_limit=0)
        """
        self.queries.append(query)

        return self._result
