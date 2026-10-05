"""
Description:
To, co wspólne dla prawdziwego `read_docs` i jego atrapy: nazwa, materiał, klasa zapytania
i lista źródeł (`cite()`). Narzędzie i atrapa różnią się wyłącznie tym, skąd biorą treść
(`search()`).

Przed — wynik odczytu:

    ReadDocsResult(sections=[ReadSection(
        section = DocSection(section_id="adm-kancelaria-edoreczenia", …),
        text    = "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → …",
    )])

Po — tekst dla modelu:

    {
      "sections": [
        {
          "section": {
            "section_id": "adm-kancelaria-edoreczenia",
            "document": "Instrukcja administratora",
            "version": "4.12",
            "date": "2026-05-04",
            …
          },
          "text": "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → …"
        }
      ]
    }

O czym pamiętać przy zmianach:

- To JEDYNE narzędzie dokumentacji, które cytuje: na listę źródeł trafia sekcja, którą model
  przeczytał, a nie taka, którą tylko zobaczył w spisie.
- Wydanie i jego data stoją przy każdej sekcji, bo instrukcja do starszej wersji wprowadza
  w błąd tak samo jak odmowa obalona nowszym zgłoszeniem.
- Treść sekcji to jedno pole tekstowe: złamania linii w JSON-ie stają się `\\n`.
"""

from app.agent_tools.base import KnowledgeSource, read_description
from app.agent_tools.docs.read_docs.models import ReadDocsQuery, ReadDocsResult
from app.agent_tools.models import SourceRef


class ReadDocsToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `read_docs`: wszystko poza samym pobraniem treści.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeReadDocsTool`) i narzędzie właściwe na Postgresie
    (`ReadDocsTool`). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł są
    te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `ReadDocsResult` albo zgłasza `UnknownSectionError`.
        2. `render_for_model()` z kontraktu robi z niego JSON.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na odczytaną sekcję.
    """

    name        = "read_docs"
    description = read_description(__file__)
    source      = "docs"
    query_model = ReadDocsQuery

    def cite(
        self,
        result: ReadDocsResult,  # np. ReadDocsResult(sections=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każdą odczytaną sekcję; tytułem jest dokument z wydaniem i tytuł sekcji.

        Example args:
            result=ReadDocsResult(sections=[ReadSection(section=DocSection(…), text="…")])

        Example result:
            [SourceRef(source="docs", item_id="adm-kancelaria-edoreczenia",
                       title="Instrukcja administratora 4.12 — Uprawnienie do kancelarii…",
                       date=date(2026, 5, 4))]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = item.section.section_id,
                title   = f"{item.section.document} {item.section.version} — {item.section.title}",
                date    = item.section.date,
            )
            for item in result.sections
        ]

        return refs
