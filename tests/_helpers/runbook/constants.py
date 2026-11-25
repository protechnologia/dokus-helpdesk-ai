"""
Description:
Stałe helpera runbooków: gdzie leżą runbooki, ich spis i CLAUDE.md, jak wygląda nazwa pliku
runbooka i jakim przedrostkiem CLAUDE.md do niego linkuje.
"""

import re
from pathlib import Path

# Korzeń repo: ten plik leży w tests/_helpers/runbook/.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Katalog runbooków i jego spis (tabela „Spis” z linkami względnymi, bez przedrostka).
RUNBOOK_DIR    = REPO_ROOT / "docs" / "runbook"
RUNBOOK_README = RUNBOOK_DIR / "README.md"

# Plik czytany na początku sesji; linkuje do runbooków ścieżką od korzenia repo.
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# Przedrostek linku do runbooka w CLAUDE.md, np. „(docs/runbook/odchudzanie-….md)”.
CLAUDE_MD_LINK_PREFIX = "docs/runbook/"

# Nazwa pliku runbooka z zasad w README: `<czynność>.md`, małymi literami i z łącznikami.
# README.md jej nie spełnia, więc nie liczy się jako runbook.
RUNBOOK_FILE_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md")
