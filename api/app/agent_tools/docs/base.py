"""
Description:
Wiersz, którym narzędzia dokumentacji pokazują modelowi sekcję. Ten sam w listingu i w obu
wyszukiwaniach, żeby identyfikator do odczytu stał zawsze w tym samym miejscu:

    [adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › Kancelaria ›
    Uprawnienie do kancelarii e-Doręczeń — Kto nadaje uprawnienie i kiedy zaczyna działać

Kolejno: identyfikator sekcji (podaje się go w `read_docs`), dokument z wydaniem, ścieżka
rozdziału zakończona tytułem sekcji i krótki opis z metryczki.

O czym pamiętać przy zmianach:

- Ten tekst jest częścią promptu — jego kształt stroi się pomiarem razem z promptami grafów.
- Wiersz nie niesie treści sekcji. Model, który chce się na niej oprzeć, musi ją odczytać,
  a tylko odczyt trafia na listę źródeł.
"""

from app.model.doc_section import DocSection

PATH_SEPARATOR = " › "


def render_section_heading(
    section: DocSection,  # np. DocSection(section_id="adm-kancelaria-edoreczenia", …)
) -> str:
    """
    Description:
    Wiersz bez opisu: identyfikator, dokument z wydaniem i miejsce sekcji w dokumencie. Tak
    zaczyna się też odczytana sekcja, pod nim stoi jej treść.

    Example args:
        section=DocSection(section_id="adm-kancelaria-edoreczenia", document="Instrukcja
                           administratora", version="4.12", chapter_path=["Uprawnienia"], …)

    Example result:
        "[adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › Uprawnienie…"
    """
    location = PATH_SEPARATOR.join([*section.chapter_path, section.title])
    heading  = f"[{section.section_id}] {section.document} {section.version} · {location}"

    return heading


def render_section_row(
    section: DocSection,  # np. DocSection(section_id="adm-kancelaria-edoreczenia", …)
) -> str:
    """
    Description:
    Pełny wiersz listingu: nagłówek sekcji i jej krótki opis z metryczki.

    Example args:
        section=DocSection(section_id="adm-kancelaria-edoreczenia", …,
                           description="Kto nadaje uprawnienie i kiedy zaczyna działać")

    Example result:
        "[adm-kancelaria-edoreczenia] Instrukcja administratora 4.12 · Uprawnienia › … — Kto
         nadaje uprawnienie i kiedy zaczyna działać"
    """
    return f"{render_section_heading(section)} — {section.description}"
