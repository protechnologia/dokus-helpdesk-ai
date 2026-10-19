import re
from pathlib import Path

# Notatki redakcyjne dla nas — nie mają prawa dotrzeć do modelu. Powielone z `api` celowo:
# usługi nie dzielą kodu, tylko kontrakt.
_HTML_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)


def read_document(
    path: Path,  # np. Path("anonymizer_app/agent_nodes/find_persons/prompt_system.md")
) -> str:
    """
    Description:
    Czyta jeden dokument markdown i wycina z niego komentarze redakcyjne. Czyta plik przy każdym
    wywołaniu, bez pamiętania: prompt poprawiany w dev działa bez restartu usługi.

    Example args:
        path=Path("anonymizer_app/agent_nodes/find_persons/prompt_system.md")

    Example result:
        "Jesteś narzędziem do anonimizacji zgłoszeń helpdesku. Wypisz z tekstu…"

    Raises:
        FileNotFoundError: brak dokumentu — błąd pakowania (musi być w obrazie)
    """
    return _HTML_COMMENT.sub("", path.read_text(encoding="utf-8")).strip()
