import json
from functools import lru_cache
from pathlib import Path

from app.model.variant_generation_set import GenerationVariantSet
from app.util.markdown import read_document

# The bundled default set. Stage 8 replaces this SOURCE with the SQL rules store, and this function
# is the seam that makes the swap invisible: every caller asks for the variants here, so none of
# them learns where they came from — the same route the outcome vocabulary and the `Popraw` style
# rules take (CLAUDE.md -> "Bramki jakości").
TEXT_DIR              = Path(__file__).parent.parent / "text"
DEFAULT_VARIANTS_FILE = TEXT_DIR / "variants.json"


@lru_cache
def get_generation_variants(path: Path = DEFAULT_VARIANTS_FILE) -> GenerationVariantSet:
    """
    Description:
    Loads the generation variants, resolving each one's prompt document into text. Cached per path
    rather than read at import time, so importing the module touches no disk and a test can point
    at its own file.

    Flow:
        1. Read the variant list — customer data describing which buttons exist.
        2. Swap each `prompt_file` for the contents of that document, editorial comments stripped.
        3. Validate the whole set, which is where an unknown key or a duplicate name fails.

    Prompt documents are resolved relative to the variant file's own directory, so a test fixture
    in `tmp_path` keeps its prompts beside itself instead of reaching into the shipped `text/`.

    Example args:
        path=Path("/code/app/text/variants.json")

    Example result:
        GenerationVariantSet(version=1, variants=[GenerationVariant(name="questions", …), …])

    Raises:
        FileNotFoundError: the variant file or one of its prompt documents is missing — a
            deployment error, not a runtime one
        ValueError: a variant declares no prompt document
        ValidationError: the set does not match the contract (unknown key, duplicate name)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    resolved             = dict(raw)
    resolved["variants"] = [
        _with_prompt_text(entry, path.parent) for entry in raw.get("variants", [])
    ]

    return GenerationVariantSet.model_validate(resolved)


def _with_prompt_text(
    entry:    dict,  # e.g. {"name": "questions", "prompt_file": "prompt_suggest_questions.md", …}
    text_dir: Path,  # e.g. Path("/code/app/text")
) -> dict:
    """
    Description:
    Turns one file-format entry into one domain-shaped entry: `prompt_file` out, `prompt` in.

    Why the two differ: the domain model carries the prompt as TEXT, because that is what a SQL
    column will hold in stage 8. The file points at a markdown document instead, so the prompt
    stays something a human reviews sentence by sentence rather than a JSON string full of escaped
    newlines (CLAUDE.md -> "Prompty").

    Raises rather than letting validation complain about a missing `prompt`: the file says
    `prompt_file` and the model says `prompt`, so pydantic's "prompt Field required" would point at
    a key the author never wrote.

    Example args:
        entry={"name": "questions", "label": "Jakie pytania zadać", "requires_hits": False,
               "prompt_file": "prompt_suggest_questions.md"}
        text_dir=Path("/code/app/text")

    Example result:
        {"name": "questions", "label": "Jakie pytania zadać", "requires_hits": False,
         "prompt": "Jesteś asystentem wdrożeniowca helpdesku…"}

    Raises:
        ValueError: the entry has no `prompt_file`
        FileNotFoundError: the document it points at is missing
    """
    prompt_file = entry.get("prompt_file")
    if prompt_file is None:
        raise ValueError(f"wariant {entry.get('name', '?')!r} bez pola 'prompt_file'")

    resolved           = {key: value for key, value in entry.items() if key != "prompt_file"}
    resolved["prompt"] = read_document(text_dir / prompt_file)

    return resolved
