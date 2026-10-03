"""
Description:
To, co wspólne dla prawdziwego `find_docs_text` i jego atrapy: nazwa, klasa argumentów i tekst
dla modelu. Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą wynik (`find()`).

Przed — wynik wyszukiwania:

    FindDocsTextResult(
        items = [MatchedSection(
            matched_by = "exact",
            snippet    = "Komunikat „Nie udało się skomunikować z serwerem” przy podpisie…",
            section    = DocSection(section_id="usr-komunikat-brak-serwera", …),
        )],
    )

Po — tekst dla modelu:

    Znalezione sekcje dokumentacji: 1 (pominięte ponad limit: 0)

    [usr-komunikat-brak-serwera] Instrukcja użytkownika 4.12 · Komunikaty błędów › Komunikat „Nie
    udało się skomunikować z serwerem” — Możliwe przyczyny komunikatu… · dopasowanie: dosłowny ciąg
    fragment: Komunikat „Nie udało się skomunikować z serwerem” przy podpisie…

O czym pamiętać przy zmianach:

- To narzędzie pomocnicze: zwraca wiersze spisu treści z fragmentem, niczego nie cytuje. Źródłem
  odpowiedzi jest dopiero sekcja odczytana przez `read_docs`.
- Wiersz sekcji jest wspólny z listingiem i wyszukiwaniem wektorowym (`tools/docs/base.py`).
"""

from abc import abstractmethod

from app.tools.base import AuxiliaryTool
from app.tools.docs.base import render_section_row
from app.tools.docs.find_docs_text.models import FindDocsTextQuery, FindDocsTextResult

# Etykiety dopasowania w tekście dla modelu.
MATCH_LABELS = {
    "exact": "dosłowny ciąg",
    "words": "słowa",
}


class FindDocsTextToolBase(AuxiliaryTool):
    """
    Description:
    Wspólna część `find_docs_text`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeFindDocsTextTool`) i narzędzie właściwe na Postgresie
    (p. 50). Każda dokłada wyłącznie `find()`, więc tekst dla modelu jest ten sam w testach i na
    produkcji.

    Flow:
        1. `run()` woła `find()` podklasy i dostaje `FindDocsTextResult`.
        2. `render()` robi z niego tekst: nagłówek z licznikami, a na sekcję wiersz spisu treści
           i dopasowany fragment.
    """

    name       = "find_docs_text"
    args_model = FindDocsTextQuery

    @abstractmethod
    async def find(
        self,
        query: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> FindDocsTextResult:
        """
        Description:
        Znajduje sekcje dokumentacji zawierające dosłowne ciągi albo słowa z zapytania, dosłowne
        trafienia najpierw, przycięte limitem.

        Example args:
            query=FindDocsTextQuery(exact=["Nie udało się skomunikować z serwerem"])

        Example result:
            FindDocsTextResult(items=[MatchedSection(matched_by="exact", …)], omitted_over_limit=0)
        """

    def render(
        self,
        result: FindDocsTextResult,  # np. FindDocsTextResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z licznikami, a na sekcję
        wiersz spisu treści z etykietą dopasowania i linia z fragmentem. Bez trafień zostaje sam
        nagłówek.

        Example args:
            result=FindDocsTextResult(items=[MatchedSection(…)], omitted_over_limit=0)

        Example result:
            Znalezione sekcje dokumentacji: 1 (pominięte ponad limit: 0)

            [usr-komunikat-brak-serwera] Instrukcja użytkownika … · dopasowanie: dosłowny ciąg
            fragment: Komunikat „Nie udało się skomunikować z serwerem” przy podpisie…
        """
        header = (
            f"Znalezione sekcje dokumentacji: {len(result.items)} "
            f"(pominięte ponad limit: {result.omitted_over_limit})"
        )

        rows = [
            f"{render_section_row(matched.section)} · "
            f"dopasowanie: {MATCH_LABELS[matched.matched_by]}\n"
            f"fragment: {matched.snippet}"
            for matched in result.items
        ]

        text = "\n\n".join([header, *rows])

        return text

    async def run(
        self,
        args: FindDocsTextQuery,  # np. FindDocsTextQuery(words="uprawnienie kancelaria")
    ) -> str:
        """
        Description:
        Wyszukuje i zwraca tekst dla modelu.

        Example args:
            args=FindDocsTextQuery(words="uprawnienie kancelaria")

        Example result:
            Znalezione sekcje dokumentacji: 2 (pominięte ponad limit: 0)

            [usr-komunikat-brak-serwera] Instrukcja użytkownika … · dopasowanie: dosłowny ciąg
            fragment: Komunikat „Nie udało się skomunikować z serwerem” przy podpisie…

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · … · dopasowanie: słowa
            fragment: Uprawnienie do kancelarii e-Doręczeń nadaje administrator…
        """
        result = await self.find(args)
        text   = self.render(result)

        return text
