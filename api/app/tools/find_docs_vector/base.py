"""
Description:
To, co wspólne dla prawdziwego `find_docs_vector` i jego atrapy: nazwa, klasa argumentów i tekst
dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindDocsVectorResult(
        items = [
            FoundSection(score=0.74, section=DocSection(section_id="adm-kancelaria-…", …)),
        ],
        dropped_below_threshold = 1,
    )

Po — tekst dla modelu:

    Znalezione sekcje dokumentacji: 1 (odcięte progiem: 1)

    [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › Kancelaria ›
    Uprawnienie do kancelarii e-Doręczeń — Kto i gdzie nadaje uprawnienie… · podobieństwo 0.74

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca wiersze spisu treści, nie treść, i niczego nie cytuje. Źródłem
  odpowiedzi jest dopiero sekcja odczytana przez `read_docs`.
- Wiersz sekcji jest wspólny z listingiem i wyszukiwaniem tekstowym (`tools/render_docs.py`).
"""

from abc import abstractmethod

from app.tools.base import AuxiliaryTool
from app.tools.find_docs_vector.models import FindDocsVectorQuery, FindDocsVectorResult
from app.tools.render_docs import render_section_row


class FindDocsVectorToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_docs_vector`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindDocsVectorTool`) i narzędzie właściwe na kolekcji
    dokumentacji w Qdrancie (p. 8). Każda dokłada wyłącznie `find()`, więc tekst dla modelu jest
    ten sam w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindDocsVectorResult`.
        2. `render()` robi z niego tekst: nagłówek z licznikami i po wierszu na sekcję.
    """

    name       = "find_docs_vector"
    args_model = FindDocsVectorQuery

    @abstractmethod
    async def find(
        self,
        query: FindDocsVectorQuery,  # np. FindDocsVectorQuery(text="uprawnienia kancelaria")
    ) -> FindDocsVectorResult:
        """
        Description:
        Znajduje sekcje dokumentacji podobne znaczeniowo do zapytania, od najbardziej podobnej,
        już przycięte progiem.

        Example args:
            query=FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            FindDocsVectorResult(items=[FoundSection(score=0.74, section=DocSection(…))],
                                 dropped_below_threshold=0)
        """

    def render(
        self,
        result: FindDocsVectorResult,  # np. FindDocsVectorResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z licznikami i po wierszu na
        sekcję, z podobieństwem na końcu. Bez trafień zostaje sam nagłówek.

        Example args:
            result=FindDocsVectorResult(items=[FoundSection(…)], dropped_below_threshold=0)

        Example result:
            Znalezione sekcje dokumentacji: 1 (odcięte progiem: 0)

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · … · podobieństwo 0.74
        """
        header = (
            f"Znalezione sekcje dokumentacji: {len(result.items)} "
            f"(odcięte progiem: {result.dropped_below_threshold})"
        )

        rows = [
            f"{render_section_row(found.section)} · podobieństwo {found.score:.2f}"
            for found in result.items
        ]

        text = "\n\n".join([header, *rows])

        return text

    async def run(
        self,
        args: FindDocsVectorQuery,  # np. FindDocsVectorQuery(text="uprawnienia kancelaria")
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu.

        Example args:
            args=FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            Znalezione sekcje dokumentacji: 2 (odcięte progiem: 0)

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · … · podobieństwo 0.74

            [adm-kancelaria-epuap] Instrukcja administratora 4.12 · … · podobieństwo 0.68
        """
        result = await self.find(args)
        text   = self.render(result)

        return text
