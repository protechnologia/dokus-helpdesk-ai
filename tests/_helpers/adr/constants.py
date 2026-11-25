"""
Description:
Stałe helpera ADR: gdzie leżą ADR-y, ich spis i CLAUDE.md, jak wygląda nazwa pliku ADR i jakim
przedrostkiem CLAUDE.md do niego linkuje.
"""

import re
from pathlib import Path

# Korzeń repo: ten plik leży w tests/_helpers/adr/.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Katalog decyzji i jego spis (tabela „Decyzje” z linkami względnymi, bez przedrostka).
ADR_DIR    = REPO_ROOT / "docs" / "adr"
ADR_README = ADR_DIR / "README.md"

# Plik czytany na początku sesji; linkuje do ADR-ów ścieżką od korzenia repo.
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# Przedrostek linku do ADR w CLAUDE.md, np. „(docs/adr/ADR-001_….md)”.
CLAUDE_MD_LINK_PREFIX = "docs/adr/"

# Nazwa pliku ADR z zasad w README: `ADR-<NNN>_<krótka-nazwa>.md`. README.md jej nie
# spełnia, więc nie liczy się jako ADR.
ADR_FILE_NAME = re.compile(r"ADR-\d{3}_[a-z0-9-]+\.md")
