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

    Dokumentacja: sekcji 2, dokumentów 2

    [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › Kancelaria ›
    Uprawnienie do kancelarii e-Doręczeń — Kto i gdzie nadaje uprawnienie…
    [usr-wysylka-status-w-toku] Instrukcja użytkownika 4.12 · Wysyłka › ePUAP › Status „W toku”
    przy wysyłce ePUAP — Co znaczy status „W toku”…

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: spis mówi, GDZIE jest instrukcja, nie co w niej stoi, i niczego nie
  cytuje. Źródłem odpowiedzi jest dopiero sekcja odczytana przez `read_docs`.
- Wiersz sekcji jest wspólny z oboma wyszukiwaniami (`tools/docs/base.py`).
- Spis jest stały między żądaniami. Przy małej dokumentacji taniej wstawić go do promptu
  systemowego niż wołać narzędziem — do rozstrzygnięcia przy właściwej dokumentacji (p. 15).
"""

from abc import abstractmethod

from app.tools.base import AuxiliaryTool
from app.tools.docs.base import render_section_row
from app.tools.docs.list_docs.models import ListDocsArgs, ListDocsResult


class ListDocsToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `list_docs`: wszystko poza pobraniem spisu.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeListDocsTool`) i narzędzie właściwe na metryczkach
    wczytanych do bazy (p. 51). Każda dokłada wyłącznie `load()`, więc tekst dla modelu jest ten
    sam w testach i na produkcji.

    Flow:
        1. `run()` woła `load()` podklasy i dostaje `ListDocsResult`.
        2. `render()` robi z niego tekst: nagłówek z licznikami i po wierszu na sekcję.
    """

    name       = "list_docs"
    args_model = ListDocsArgs

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

    def render(
        self,
        result: ListDocsResult,  # np. ListDocsResult(sections=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z liczbą sekcji i dokumentów
        oraz po wierszu na sekcję. Przy pustej dokumentacji zostaje sam nagłówek.

        Example args:
            result=ListDocsResult(sections=[DocSection(…), DocSection(…)])

        Example result:
            Dokumentacja: sekcji 2, dokumentów 1

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · … — Kto i gdzie…
            [adm-kancelaria-epuap] Instrukcja administratora 4.12 · … — Kto nadaje…
        """
        documents = {(section.document, section.version) for section in result.sections}
        header    = f"Dokumentacja: sekcji {len(result.sections)}, dokumentów {len(documents)}"

        # --- pusta dokumentacja: nie ma wierszy do pokazania ---
        if not result.sections:
            return header

        rows = "\n".join(render_section_row(section) for section in result.sections)
        text = f"{header}\n\n{rows}"

        return text

    async def run(
        self,
        args: ListDocsArgs,  # np. ListDocsArgs()
    ) -> str:
        """
        Description:
        Pobiera spis treści i zwraca tekst dla modelu.

        Example args:
            args=ListDocsArgs()

        Example result:
            Dokumentacja: sekcji 4, dokumentów 2

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · … — Kto i gdzie…
            …
        """
        result = await self.load()
        text   = self.render(result)

        return text
