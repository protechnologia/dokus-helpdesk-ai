"""
Description:
ADR-y w repo i linki do nich: które pliki ADR leżą w `docs/adr/` i do których z nich linkuje
podany tekst. Test linków porównuje nimi katalog ze spisem w README i z CLAUDE.md.

| funkcja              | co zwraca                                           |
|----------------------|-----------------------------------------------------|
| `adr_files()`        | nazwy plików ADR w `docs/adr/`, posortowane         |
| `linked_adr_files()` | nazwy plików ADR, do których linkuje tekst Markdown |
| `claude_md_links()`  | nazwy plików ADR, do których linkuje CLAUDE.md      |
| `readme_links()`     | nazwy plików ADR ze spisu w `docs/adr/README.md`    |

Przykład: tekst „Opis ([ADR-001](docs/adr/ADR-001_zapytanie.md)).” z przedrostkiem
`docs/adr/` daje `{"ADR-001_zapytanie.md"}`.
"""

import re
from pathlib import Path

from tests._helpers.adr.constants import (
    ADR_DIR,
    ADR_FILE_NAME,
    ADR_README,
    CLAUDE_MD,
    CLAUDE_MD_LINK_PREFIX,
)


def adr_files(
    directory: Path = ADR_DIR,  # np. Path("docs/adr")
) -> list[str]:
    """
    Description:
    Nazwy plików ADR w katalogu decyzji, posortowane. Plik liczy się jako ADR, gdy jego nazwa
    ma kształt z zasad README; sam README nie jest ADR.

    Example args:
        directory=Path("docs/adr")

    Example result:
        ["ADR-001_zapytanie-w-ksztalcie-indeksu.md", …, "ADR-009_zgodnosc-przyczyn-…md"]
    """
    names = sorted(path.name for path in directory.iterdir() if ADR_FILE_NAME.fullmatch(path.name))

    return names


def linked_adr_files(
    text:   str,  # np. "([ADR-001](docs/adr/ADR-001_zapytanie.md))"
    prefix: str,  # np. "docs/adr/" w CLAUDE.md, "" w spisie README
) -> set[str]:
    """
    Description:
    Nazwy plików ADR, do których tekst Markdown ma link z podanym przedrostkiem ścieżki. Linki
    do innych plików i ścieżki z innym przedrostkiem pomija.

    Example args:
        text="Reguła ([ADR-001](docs/adr/ADR-001_zapytanie.md)), zob. [README](README.md)."
        prefix="docs/adr/"

    Example result:
        {"ADR-001_zapytanie.md"}
    """
    pattern = re.compile(rf"\]\({re.escape(prefix)}({ADR_FILE_NAME.pattern})\)")
    linked  = set(pattern.findall(text))

    return linked


def claude_md_links() -> set[str]:
    """
    Description:
    Nazwy plików ADR, do których linkuje CLAUDE.md (ścieżką `docs/adr/<plik>`).

    Example args:
        (brak)

    Example result:
        {"ADR-001_zapytanie-w-ksztalcie-indeksu.md", …}
    """
    return linked_adr_files(CLAUDE_MD.read_text(encoding="utf-8"), prefix=CLAUDE_MD_LINK_PREFIX)


def readme_links() -> set[str]:
    """
    Description:
    Nazwy plików ADR, do których linkuje `docs/adr/README.md` — w praktyce wiersze spisu
    decyzji, bo linki w README są względne, bez przedrostka katalogu.

    Example args:
        (brak)

    Example result:
        {"ADR-001_zapytanie-w-ksztalcie-indeksu.md", …}
    """
    return linked_adr_files(ADR_README.read_text(encoding="utf-8"), prefix="")
