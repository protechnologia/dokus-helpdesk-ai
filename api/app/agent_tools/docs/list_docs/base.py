"""
Description:
To, co wspólne dla prawdziwego `list_docs` i jego atrapy: nazwa, klasa argumentów i tekst dla
modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą spis (`load()`).

Przed — spis treści:

    ListDocsResult(sections=[
        DocSection(section_id="adm-kancelaria-edoreczenia", …),
        DocSection(section_id="usr-wysylka-status-w-toku", …),
    ])

Po — tekst dla modelu:

    {
      "sections": [
        {
          "section_id": "adm-kancelaria-edoreczenia",
          "document": "Instrukcja administratora",
          "version": "4.12",
          "date": "2026-05-04",
          "chapter_path": ["Uprawnienia", "Kancelaria"],
          "title": "Uprawnienie do kancelarii e-Doręczeń",
          "description": "Kto i gdzie nadaje uprawnienie do kancelarii e-Doręczeń i kiedy działa"
        },
        …
      ]
    }

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: spis mówi, GDZIE jest instrukcja, nie co w niej stoi, i niczego nie
  cytuje. Źródłem odpowiedzi jest dopiero sekcja odczytana przez `read_docs`.
- Opis sekcji (`DocSection`) jest ten sam w obu wyszukiwaniach.
- Spis jest stały między żądaniami. Przy małej dokumentacji taniej wstawić go do promptu
  systemowego niż wołać narzędziem — do rozstrzygnięcia przy właściwej dokumentacji (p. 15).
"""

from abc import abstractmethod

from app.agent_tools.base import AuxiliaryTool, read_description, result_as_json
from app.agent_tools.docs.list_docs.models import ListDocsArgs, ListDocsResult


class ListDocsToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `list_docs`: wszystko poza pobraniem spisu.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeListDocsTool`) i narzędzie właściwe na Postgresie
    (`ListDocsTool`). Każda dokłada wyłącznie `load()`, więc tekst dla modelu jest ten sam
    w testach i na produkcji.

    Flow:
        1. `run()` woła `load()` podklasy i dostaje `ListDocsResult`.
        2. Wynik idzie do modelu jako JSON (`result_as_json()`).
    """

    name        = "list_docs"
    description = read_description(__file__)
    args_model  = ListDocsArgs

    @abstractmethod
    async def load(self) -> ListDocsResult:
        """
        Description:
        Pobiera spis treści całej dokumentacji, w kolejności dokumentów i sekcji.

        Example args:
            (brak)

        Example result:
            ListDocsResult(sections=[DocSection(section_id="adm-kancelaria-edoreczenia", …), …])
        """

    async def run(
        self,
        args: ListDocsArgs,  # np. ListDocsArgs()
    ) -> str:
        """
        Description:
        Pobiera spis treści i zwraca tekst dla modelu: JSON wyniku.

        Example args:
            args=ListDocsArgs()

        Example result:
            {"sections": [{"section_id": "adm-kancelaria-edoreczenia", "document": "…", …}, …]}
        """
        result = await self.load()
        text   = result_as_json(result)

        return text
