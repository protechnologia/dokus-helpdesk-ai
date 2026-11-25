"""
Description:
Runbooki w repo i linki do nich: które pliki runbooków leżą w `docs/runbook/` i do których
z nich linkuje podany tekst. Test linków porównuje nimi katalog ze spisem w README
i z CLAUDE.md.

| funkcja                  | co zwraca                                               |
|--------------------------|---------------------------------------------------------|
| `runbook_files()`        | nazwy plików runbooków w `docs/runbook/`, posortowane   |
| `linked_runbook_files()` | nazwy plików runbooków, do których linkuje tekst        |
| `claude_md_links()`      | nazwy plików runbooków, do których linkuje CLAUDE.md    |
| `readme_links()`         | nazwy plików runbooków ze spisu w `docs/runbook/README.md` |

Przykład: tekst „Przebieg: [RB-001](docs/runbook/RB-001_odchudzanie.md).” z przedrostkiem
`docs/runbook/` daje `{"RB-001_odchudzanie.md"}`.
"""

import re
from pathlib import Path

from tests._helpers.runbook.constants import (
    CLAUDE_MD,
    CLAUDE_MD_LINK_PREFIX,
    RUNBOOK_DIR,
    RUNBOOK_FILE_NAME,
    RUNBOOK_README,
)


def runbook_files(
    directory: Path = RUNBOOK_DIR,  # np. Path("docs/runbook")
) -> list[str]:
    """
    Description:
    Nazwy plików runbooków w katalogu, posortowane. Plik liczy się jako runbook, gdy jego nazwa
    ma kształt z zasad README; sam README nie jest runbookiem.

    Example args:
        directory=Path("docs/runbook")

    Example result:
        ["RB-001_odchudzanie-podsekcji-claude-md.md", "RB-002_pod-runpod-z-bielikiem.md"]
    """
    names = sorted(
        path.name for path in directory.iterdir() if RUNBOOK_FILE_NAME.fullmatch(path.name)
    )

    return names


def linked_runbook_files(
    text:   str,  # np. "Przebieg: [RB-001](docs/runbook/RB-001_odchudzanie.md)."
    prefix: str,  # np. "docs/runbook/" w CLAUDE.md, "" w spisie README
) -> set[str]:
    """
    Description:
    Nazwy plików runbooków, do których tekst Markdown ma link z podanym przedrostkiem ścieżki.
    Linki do innych plików i ścieżki z innym przedrostkiem pomija.

    Example args:
        text="Przebieg: [RB-001](docs/runbook/RB-001_odchudzanie.md), zob. [ADR](../adr/README.md)."
        prefix="docs/runbook/"

    Example result:
        {"RB-001_odchudzanie.md"}
    """
    pattern = re.compile(rf"\]\({re.escape(prefix)}({RUNBOOK_FILE_NAME.pattern})\)")
    linked  = set(pattern.findall(text))

    return linked


def claude_md_links() -> set[str]:
    """
    Description:
    Nazwy plików runbooków, do których linkuje CLAUDE.md (ścieżką `docs/runbook/<plik>`).

    Example args:
        (brak)

    Example result:
        {"RB-001_odchudzanie-podsekcji-claude-md.md", …}
    """
    return linked_runbook_files(CLAUDE_MD.read_text(encoding="utf-8"), prefix=CLAUDE_MD_LINK_PREFIX)


def readme_links() -> set[str]:
    """
    Description:
    Nazwy plików runbooków, do których linkuje `docs/runbook/README.md` — w praktyce wiersze
    spisu, bo linki w README są względne, bez przedrostka katalogu.

    Example args:
        (brak)

    Example result:
        {"RB-001_odchudzanie-podsekcji-claude-md.md", …}
    """
    return linked_runbook_files(RUNBOOK_README.read_text(encoding="utf-8"), prefix="")
