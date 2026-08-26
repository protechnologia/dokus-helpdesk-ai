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
        2. Swap each variant's two document references for their contents, editorial comments
           stripped.
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
        ValueError: a variant is missing one of its two prompt document references
        ValidationError: the set does not match the contract (unknown key, duplicate name)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    resolved             = dict(raw)
    resolved["variants"] = [
        _with_prompt_text(entry, path.parent) for entry in raw.get("variants", [])
    ]

    return GenerationVariantSet.model_validate(resolved)


# The two document references the file format uses, mapped onto the two fields the domain model
# carries. Written out as a pair because the loader has to do the same thing to both.
_DOCUMENT_FIELDS = {
    "system_prompt_file": "system_prompt",
    "user_prompt_file":   "user_prompt",
}


def _with_prompt_text(
    entry:    dict,  # e.g. {"name": "questions", "user_prompt_file": "…_user.md", …}
    text_dir: Path,  # e.g. Path("/code/app/text")
) -> dict:
    """
    Description:
    Turns one file-format entry into one domain-shaped entry: the two document references out,
    their contents in.

    Why the two shapes differ: the domain model carries prompts as TEXT, because that is what SQL
    columns will hold in stage 8. The file points at markdown documents instead, so a prompt stays
    something a human reviews sentence by sentence rather than a JSON string full of escaped
    newlines (CLAUDE.md -> "Prompty").

    Raises rather than letting validation complain about a missing `user_prompt`: the file says
    `user_prompt_file` and the model says `user_prompt`, so pydantic's "Field required" would point
    at a key the author never wrote.

    Example args:
        entry={"name": "questions", "label": "Jakie pytania zadać", "requires_hits": False,
               "system_prompt_file": "prompt_suggest_questions_system.md",
               "user_prompt_file": "prompt_suggest_questions_user.md"}
        text_dir=Path("/code/app/text")

    Example result:
        {"name": "questions", "label": "Jakie pytania zadać", "requires_hits": False,
         "system_prompt": "Jesteś asystentem wdrożeniowca…", "user_prompt": "Zaproponuj pytania…"}

    Raises:
        ValueError: the entry is missing one of the two document references
        FileNotFoundError: a document it points at is missing
    """
    resolved = {key: value for key, value in entry.items() if key not in _DOCUMENT_FIELDS}

    for reference, field in _DOCUMENT_FIELDS.items():
        document = entry.get(reference)
        if document is None:
            raise ValueError(f"wariant {entry.get('name', '?')!r} bez pola {reference!r}")

        resolved[field] = read_document(text_dir / document)

    return resolved
