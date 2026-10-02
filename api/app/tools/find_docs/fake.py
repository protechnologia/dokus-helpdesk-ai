from collections.abc import Sequence
from datetime import date

from app.tools.base import KnowledgeSource
from app.tools.find_docs.models import FindDocsQuery, FindDocsResult, FoundDoc
from app.tools.models import SourceRef


def default_docs() -> list[FoundDoc]:
    """
    Description:
    Wbudowany zestaw atrapy: dwa zmyślone fragmenty dokumentacji — jeden o uprawnieniach,
    jeden z ostrzeżeniem o kroku nieodwracalnym, bo właśnie takie ostrzeżenia agent ma przenosić
    do odpowiedzi.

    Example args:
        (brak)

    Example result:
        [FoundDoc(fragment_id="doc-1", score=0.74, document="Instrukcja administratora", …), …]
    """
    return [
        FoundDoc(
            fragment_id = "doc-1",
            score       = 0.74,
            document    = "Instrukcja administratora",
            version     = "4.12",
            date        = date(2026, 5, 4),
            text        = "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia "
                          "→ Uprawnienia → Kancelaria; działa po ponownym zalogowaniu.",
        ),
        FoundDoc(
            fragment_id = "doc-2",
            score       = 0.68,
            document    = "Instrukcja użytkownika",
            version     = "4.12",
            date        = date(2026, 5, 4),
            text        = "Status „W toku” przy wysyłce ePUAP oznacza nadawanie w trakcie — "
                          "ponowna wysyłka utworzy drugie, nieodwracalne doręczenie.",
        ),
    ]


class FakeFindDocs(KnowledgeSource):
    """
    Description:
    Atrapa `find_docs`: zamiast kolekcji dokumentacji zwraca ustalony zestaw fragmentów, zawsze
    ten sam, ze stałymi id. Ta sama rola co `FakeFindTickets`.

    Flow:
        1. Test tworzy ją z własnymi fragmentami albo z zestawem wbudowanym.
        2. Każde `search()` zapisuje zapytanie w `queries` i zwraca ten sam wynik.
        3. `render_for_model()` i `cite()` działają na wyniku jak w prawdziwym narzędziu.
    """

    name        = "find_docs"
    query_model = FindDocsQuery

    def __init__(
        self,
        docs:                    Sequence[FoundDoc] | None = None,  # np. [FoundDoc(…)]
        dropped_below_threshold: int = 0,                           # np. 1
    ):
        """
        Description:
        Ustala, co atrapa będzie zwracać, i zakłada dziennik zapytań.

        Example args:
            docs=None
            dropped_below_threshold=0

        Example result:
            FakeFindDocs zwracająca wbudowane dwa fragmenty przy każdym wyszukaniu
        """
        self._result = FindDocsResult(
            items                   = list(docs) if docs is not None else default_docs(),
            dropped_below_threshold = dropped_below_threshold,
        )

        # Publiczne celowo: testy sprawdzają, o co pytał agent.
        self.queries: list[FindDocsQuery] = []

    async def search(
        self,
        query: FindDocsQuery,  # np. FindDocsQuery(text="uprawnienia kancelaria")
    ) -> FindDocsResult:
        """
        Description:
        Zapisuje zapytanie i zwraca ustalony wynik — niezależnie od treści zapytania.

        Example args:
            query=FindDocsQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            FindDocsResult(items=[FoundDoc(fragment_id="doc-1", …), …], dropped_below_threshold=0)
        """
        self.queries.append(query)

        return self._result

    def render_for_model(
        self,
        result: FindDocsResult,  # np. FindDocsResult(items=[…])
    ) -> str:
        """
        Description:
        Prosty tekst dla modelu: liczba fragmentów i po jednym bloku na fragment, z dokumentem
        i wersją, żeby model mógł zaznaczyć, którego wydania dotyczy instrukcja.

        Example args:
            result=FindDocsResult(items=[FoundDoc(…)], dropped_below_threshold=0)

        Example result:
            "Znalezione fragmenty dokumentacji: 1 (odcięte progiem: 0)\\n\\n[doc-1] …"
        """
        header = (
            f"Znalezione fragmenty dokumentacji: {len(result.items)} "
            f"(odcięte progiem: {result.dropped_below_threshold})"
        )

        blocks = [
            f"[{found.fragment_id}] {found.document}, wersja {found.version} · "
            f"podobieństwo {found.score:.2f}\n"
            f"{found.text}"
            for found in result.items
        ]

        return "\n\n".join([header, *blocks])

    def cite(
        self,
        result: FindDocsResult,  # np. FindDocsResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każdy fragment z wyniku; tytułem jest dokument z wersją.

        Example args:
            result=FindDocsResult(items=[FoundDoc(fragment_id="doc-1", …)])

        Example result:
            [SourceRef(source="find_docs", item_id="doc-1",
                       title="Instrukcja administratora 4.12", …)]
        """
        return [
            SourceRef(
                source  = self.name,
                item_id = found.fragment_id,
                title   = f"{found.document} {found.version}",
                score   = found.score,
                date    = found.date,
            )
            for found in result.items
        ]
