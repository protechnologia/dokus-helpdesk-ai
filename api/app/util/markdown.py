import re
from functools import lru_cache
from pathlib import Path

# Editorial notes for us; they must never reach the model. Every prompt document in `text/` opens
# with one saying which change regime the file belongs to (our code vs. customer data), and that
# note is written for a reviewer, not for the model that will be handed the text.
_HTML_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)


@lru_cache
def read_document(path: Path) -> str:   # e.g. Path("/code/app/text/prompt_suggest_questions.md")
    """
    Description:
    Reads one markdown document and strips our editorial comments. Knows nothing about tickets or
    prompts — it reads a file and removes HTML comments — which is why it lives in `util/` rather
    than next to either of its callers.

    Shared on purpose: the rule "an editorial note must not reach the model" holds for the parsing
    prompt and for every generation variant alike, and a second copy of this regex would be a
    second place to forget it.

    Cached per path, so a file is read once per process rather than on every ticket of a
    1500-ticket run.

    Example args:
        path=Path("/code/app/text/prompt_suggest_questions.md")

    Example result:
        "Jesteś asystentem wdrożeniowca helpdesku. Na podstawie zgłoszenia…"

    Raises:
        FileNotFoundError: the document is missing — a packaging error (it must be inside the
            image, not only in the developer's checkout)
    """
    return _HTML_COMMENT.sub("", path.read_text(encoding="utf-8")).lstrip()
