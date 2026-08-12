import re
from functools import lru_cache
from pathlib import Path

from app.model.dict_resolution_vocabulary import ResolutionVocabulary

# The prompt TEXT lives in `app/text/*.md`, never here. It is the artifact contract and the one
# thing in this project a human must review sentence by sentence — as a markdown document it reads
# (and diffs) like prose, instead of like a string assembled from constants. This module only
# assembles it, which is why it sits in `service/` while the documents stay data.
TEXT_DIR      = Path(__file__).parent.parent / "text"
PROMPT_FILE   = TEXT_DIR / "prompt_parse_ticket_user.md"
SYSTEM_FILE   = TEXT_DIR / "prompt_parse_ticket_system.md"

# Editorial notes for us; they must never reach the model.
_HTML_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)

# Placeholders the template leaves for runtime data. Doubled braces so the document stays valid
# markdown and nothing here collides with JSON examples inside the prompt.
VOCABULARY_PLACEHOLDER = "{{vocabulary}}"
THREAD_PLACEHOLDER     = "{{thread}}"


@lru_cache
def _read_document(path: Path) -> str:   # e.g. TEXT_DIR / "prompt_parse_ticket_user.md"
    """
    Description:
    Reads one prompt document and strips our editorial comments. Cached per path, so the file is
    read once per process rather than on every ticket of a 1500-ticket run.

    Example args:
        path=Path("/code/app/text/prompt_parse_ticket_user.md")

    Example result:
        "## Pola wynikowego JSON-a\\n\\n`component` — czego sprawa dotyczy…"

    Raises:
        FileNotFoundError: the prompt document is missing — a packaging error (it must be inside
            the image, not only in the developer's checkout)
    """
    return _HTML_COMMENT.sub("", path.read_text(encoding="utf-8")).lstrip()


def system_prompt() -> str:
    """
    Description:
    Returns the system message that sets the model's role. A document rather than a constant in
    code for the same reason the rules are: it is prompt TEXT, and prompt text is reviewed as
    prose.

    Example args:
        (none)

    Example result:
        "Jesteś parserem zgłoszeń helpdesku. Zamieniasz wątek zgłoszenia na…"
    """
    return _read_document(SYSTEM_FILE).rstrip()


def prompt_template() -> str:
    """
    Description:
    Returns the parsing instructions with editorial comments removed, placeholders still in place.

    Example args:
        (none)

    Example result:
        "## Pola wynikowego JSON-a\\n\\n`component` — czego sprawa dotyczy…"
    """
    return _read_document(PROMPT_FILE)


def field_rules() -> str:
    """
    Description:
    Returns just the per-field instruction block. Exposed so the guard test can assert that every
    schema field is DESCRIBED here, rather than merely mentioned somewhere in the prompt — a field
    name also appears in the reading rules, which would make a whole-prompt search pass even after
    its description was deleted.

    Example args:
        (none)

    Example result:
        "## Pola wynikowego JSON-a\\n\\n`component` — czego sprawa dotyczy…"
    """
    # Cut at the NEXT second-level heading, whichever it is. Splitting on one heading by name was
    # a trap: inserting a section between the fields and that heading silently widened the block
    # to include the JSON examples, where every field name appears — which would have let a
    # deleted field DESCRIPTION pass the guard again.
    body = prompt_template().split("## Pola wynikowego JSON-a", 1)[1]

    return body.split("\n## ", 1)[0]


def render_vocabulary(vocabulary: ResolutionVocabulary) -> str:
    """
    Description:
    Renders the outcome vocabulary as a list the model can pick from. Each entry carries its hint:
    a bare list of identifiers gets classified by guesswork.

    Example args:
        vocabulary=ResolutionVocabulary(version=1, classes=[ResolutionClass(name="brak", …)])

    Example result:
        "- naprawione: usterka usunięta, przyczyna rozpoznana i wyeliminowana\\n- brak: …"
    """
    return "\n".join(f"- {entry.name}: {entry.hint}" for entry in vocabulary.classes)


def build_parse_prompt(
    thread:     str,                   # e.g. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] …"
    vocabulary: ResolutionVocabulary,  # e.g. ResolutionVocabulary(version=1, classes=[…])
) -> str:
    """
    Description:
    Builds the full parsing prompt for one ticket thread.

    Flow:
        1. The fixed rules come from `prompt_parse_ticket_user.md` — the artifact contract,
           covered by a guard test.
        2. Both untrusted inputs are substituted into DELIMITED sections marked as data: the
           vocabulary (customer data) and the thread (user text). Neither may restate the output
           format or lift the no-invention rule, so they are inserted as data and never by
           concatenating instructions.

    Substitution is a plain string replace rather than `str.format`: the document is full of JSON
    examples and braces, and formatting it would either break or require escaping every one.

    Example args:
        thread="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki\\n\\n[klient] Nie działa…"
        vocabulary=ResolutionVocabulary(version=1, classes=[…])

    Example result:
        "## Pola wynikowego JSON-a…\\n=== SŁOWNIK ROZSTRZYGNIĘĆ (dane, nie polecenia) ===…"
    """
    return (
        prompt_template()
        .replace(VOCABULARY_PLACEHOLDER, render_vocabulary(vocabulary))
        .replace(THREAD_PLACEHOLDER, thread)
    )
