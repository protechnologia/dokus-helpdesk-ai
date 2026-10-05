"""
Description:
To, co wspólne dla prawdziwego `find_docs_vector` i jego atrapy: nazwa, klasa argumentów i tekst
dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindDocsVectorResult(
        sections = [
            FoundSection(score=0.74, section=DocSection(section_id="adm-kancelaria-…", …)),
        ],
        dropped_below_threshold = 1,
    )

Po — tekst dla modelu:

    {
      "sections": [
        {
          "score": 0.74,
          "section": {
            "section_id": "adm-kancelaria-edoreczenia",
            "document": "Instrukcja administratora",
            "version": "4.12",
            "date": "2026-05-04",
            "chapter_path": ["Uprawnienia", "Kancelaria"],
            "title": "Uprawnienie do kancelarii e-Doręczeń",
            "description": "Kto i gdzie nadaje uprawnienie do kancelarii e-Doręczeń i kiedy działa"
          }
        }
      ],
      "dropped_below_threshold": 1
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca opisy sekcji, nie treść, i niczego nie cytuje. Źródłem
  odpowiedzi jest dopiero sekcja odczytana przez `read_docs`.
- Opis sekcji (`DocSection`) jest ten sam w spisie treści i w wyszukiwaniu tekstowym, więc
  identyfikator do odczytu stoi zawsze w tym samym polu.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.docs.find_docs_vector.models import FindDocsVectorQuery, FindDocsVectorResult


class FindDocsVectorToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_docs_vector`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindDocsVectorTool`) i narzędzie właściwe na kolekcji
    dokumentacji w Qdrancie (`FindDocsVectorTool`). Każda dokłada wyłącznie `find()`, więc tekst
    dla modelu jest ten sam w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindDocsVectorResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "find_docs_vector"
    description = read_description(__file__)
    args_model  = FindDocsVectorQuery

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
            FindDocsVectorResult(sections=[FoundSection(score=0.74, section=DocSection(…))],
                                 dropped_below_threshold=0)
        """

    async def run(
        self,
        args: FindDocsVectorQuery,  # np. FindDocsVectorQuery(text="uprawnienia kancelaria")
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

        Example result:
            {"sections": [{"score": 0.74, "section": {"section_id": "adm-kancelaria-…", …}}],
             "dropped_below_threshold": 0}
        """
        result = await self.find(args)
        text   = result_as_json(result)

        return text
