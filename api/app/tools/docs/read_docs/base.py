"""
Description:
To, co wspólne dla prawdziwego `read_docs` i jego atrapy: nazwa, materiał, klasa zapytania, tekst
dla modelu (`render_for_model()`) i lista źródeł (`cite()`). Narzędzie i atrapa różnią się
wyłącznie tym, skąd biorą treść (`search()`).

Przed — wynik odczytu:

    ReadDocsResult(items=[ReadSection(
        section = DocSection(section_id="adm-kancelaria-edoreczenia", …),
        text    = "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → …",
    )])

Po — tekst dla modelu:

    Odczytane sekcje dokumentacji: 1

    [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › Kancelaria ›
    Uprawnienie do kancelarii e-Doręczeń
    wydanie z 2026-05-04
    Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → …

O czym pamiętać przy zmianach:

- To JEDYNE narzędzie dokumentacji, które cytuje: na listę źródeł trafia sekcja, którą model
  przeczytał, a nie taka, którą tylko zobaczył w spisie.
- Data wydania stoi przy każdej sekcji, bo instrukcja do starszej wersji wprowadza w błąd tak
  samo jak odmowa obalona nowszym zgłoszeniem.
- Źródło z tego narzędzia nie ma podobieństwa (`score=None`): sekcję wskazano po identyfikatorze.
"""

from app.tools.base import KnowledgeSource
from app.tools.docs.base import render_section_heading
from app.tools.docs.read_docs.models import ReadDocsQuery, ReadDocsResult, ReadSection
from app.tools.models import SourceRef

NO_DATE = "(bez daty)"


def render_read_section(
    item: ReadSection,  # np. ReadSection(section=DocSection(…), text="Uprawnienie do kancelarii…")
) -> str:
    """
    Description:
    Jedna odczytana sekcja w tekście dla modelu: nagłówek sekcji, data wydania i treść.

    Example args:
        item=ReadSection(section=DocSection(section_id="adm-kancelaria-edoreczenia", …), text="…")

    Example result:
        [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › …
        wydanie z 2026-05-04
        Uprawnienie do kancelarii e-Doręczeń nadaje administrator…
    """
    released = item.section.date.isoformat() if item.section.date is not None else NO_DATE

    lines = [
        render_section_heading(item.section),
        f"wydanie z {released}",
        item.text,
    ]

    return "\n".join(lines)


class ReadDocsToolBase(KnowledgeSource):
    """
    Description:
    Wspólna część `read_docs`: wszystko poza samym pobraniem treści.

    Do czego:
    Po tej klasie dziedziczą atrapa (`FakeReadDocsTool`) i narzędzie właściwe (p. 52). Każda dokłada
    wyłącznie `search()`, więc tekst dla modelu i lista źródeł są te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `ReadDocsResult` albo zgłasza `UnknownSectionError`.
        2. `render_for_model()` robi z niego tekst: nagłówek i sekcje z treścią.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na odczytaną sekcję.
    """

    name        = "read_docs"
    source      = "docs"
    query_model = ReadDocsQuery

    def render_for_model(
        self,
        result: ReadDocsResult,  # np. ReadDocsResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: liczba odczytanych sekcji i każda
        sekcja z nagłówkiem, datą wydania i treścią.

        Example args:
            result=ReadDocsResult(items=[ReadSection(…)])

        Example result:
            Odczytane sekcje dokumentacji: 1

            [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › …
            wydanie z 2026-05-04
            Uprawnienie do kancelarii e-Doręczeń nadaje administrator…
        """
        header   = f"Odczytane sekcje dokumentacji: {len(result.items)}"
        sections = [render_read_section(item) for item in result.items]

        text = "\n\n".join([header, *sections])

        return text

    def cite(
        self,
        result: ReadDocsResult,  # np. ReadDocsResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każdą odczytaną sekcję; tytułem jest dokument z wydaniem i tytuł sekcji,
        podobieństwa brak.

        Example args:
            result=ReadDocsResult(items=[ReadSection(section=DocSection(…), text="…")])

        Example result:
            [SourceRef(source="docs", item_id="adm-kancelaria-edoreczenia",
                       title="Instrukcja administratora 4.12 — Uprawnienie do kancelarii…",
                       score=None, date=date(2026, 5, 4))]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = item.section.section_id,
                title   = f"{item.section.document} {item.section.version} — {item.section.title}",
                score   = None,
                date    = item.section.date,
            )
            for item in result.items
        ]

        return refs
