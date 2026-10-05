"""
Description:
To, co wspólne dla prawdziwego `find_docs_text` i jego atrapy: nazwa, klasa argumentów i tekst
dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindDocsTextResult(
        sections = [MatchedSection(
            matched_by = "exact",
            section    = DocSection(section_id="usr-komunikat-brak-serwera", …),
        )],
    )

Po — tekst dla modelu:

    {
      "sections": [
        {
          "matched_by": "exact",
          "section": {
            "section_id": "usr-komunikat-brak-serwera",
            "document": "Instrukcja użytkownika",
            "version": "4.12",
            …
          }
        }
      ],
      "omitted_over_limit": 0
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca opisy sekcji, niczego nie cytuje. Źródłem odpowiedzi jest
  dopiero sekcja odczytana przez `read_docs`.
- Fragmentu treści w wyniku nie ma: treść daje wyłącznie odczyt, inaczej model mógłby oprzeć
  się na czymś, co nie trafi na listę źródeł.
- `matched_by` nosi nazwę pola, którym agent pytał: `exact` albo `words`.
- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.docs.find_docs_text.models import FindDocsTextQuery, FindDocsTextResult


class FindDocsTextToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_docs_text`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindDocsTextTool`) i narzędzie właściwe na Postgresie
    (`FindDocsTextTool`). Każda dokłada wyłącznie `find()`, więc tekst dla modelu jest ten sam
    w testach i na produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindDocsTextResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "find_docs_text"
    description = read_description(__file__)
    args_model  = FindDocsTextQuery

    @abstractmethod
    async def find(
        self,
        query: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> FindDocsTextResult:
        """
        Description:
        Znajduje sekcje dokumentacji zawierające frazę z `exact` albo wszystkie słowa z `words`,
        znalezione frazą najpierw, przycięte limitem.

        Example args:
            query=FindDocsTextQuery(exact="Nie udało się skomunikować z serwerem")

        Example result:
            FindDocsTextResult(sections=[MatchedSection(matched_by="exact", …)],
                               omitted_over_limit=0)
        """

    async def run(
        self,
        args: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=FindDocsTextQuery(words="uprawnienie kancelaria")

        Example result:
            {"sections": [{"matched_by": "words",
                           "section": {"section_id": "adm-kancelaria-edoreczenia", …}}],
             "omitted_over_limit": 0}
        """
        result = await self.find(args)
        text   = result_as_json(result)

        return text
