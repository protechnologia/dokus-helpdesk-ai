import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.service.loader_variants import DEFAULT_VARIANTS_FILE, get_generation_variants

# One well-formed entry, spread out so a test can change the one field it is about.
_ENTRY = {
    "name":          "questions",
    "label":         "Jakie pytania zadać",
    "requires_hits": False,
    "prompt_file":   "prompt_suggest_questions.md",
}


def _variant_file(
    tmp_path: Path,                     # e.g. Path("/tmp/pytest-0/test_x0")
    entries:  list[dict],               # e.g. [{"name": "questions", "prompt_file": "q.md", …}]
    prompts:  dict[str, str] | None = None,  # e.g. {"q.md": "Zadaj pytania…"}
    version:  int = 1,
) -> Path:
    """
    Description:
    Writes a variants file plus the prompt document each entry points at, and returns its path.
    The only axis this file has — "a variant set on disk" — so every test builds its case here
    rather than assembling JSON by hand.

    Documents land beside the variants file because that is where the loader resolves them from.
    An entry may deliberately point at a document this helper is not given, which is how the
    missing-document case is set up.

    Example args:
        tmp_path=Path("/tmp/pytest-0/test_x0")
        entries=[{"name": "questions", "label": "Pytania", "requires_hits": False,
                  "prompt_file": "q.md"}]
        prompts={"q.md": "Zadaj pytania diagnostyczne."}

    Example result:
        Path("/tmp/pytest-0/test_x0/variants.json")
    """
    prompts = prompts or {}

    for entry in entries:
        document = entry.get("prompt_file")
        if document in prompts:
            (tmp_path / document).write_text(prompts[document], encoding="utf-8")

    path = tmp_path / "variants.json"
    path.write_text(json.dumps({"version": version, "variants": entries}), encoding="utf-8")

    return path


def test_variant_carries_the_text_of_its_prompt_document(tmp_path: Path) -> None:
    """Entry pointing at a document → variant's `prompt` is that document's text."""
    path = _variant_file(tmp_path, [_ENTRY], {"prompt_suggest_questions.md": "Zadaj pytania."})

    variant = get_generation_variants(path).get("questions")

    assert variant is not None
    assert variant.prompt == "Zadaj pytania."


def test_editorial_comments_never_reach_the_prompt(tmp_path: Path) -> None:
    """Document opening with an editorial note → the note is stripped, the instruction stays."""
    document = "<!-- DANE KLIENTA, edytowalne w runtime -->\nZadaj pytania diagnostyczne."
    path     = _variant_file(tmp_path, [_ENTRY], {"prompt_suggest_questions.md": document})

    prompt = get_generation_variants(path).get("questions").prompt

    assert "DANE KLIENTA" not in prompt
    assert prompt == "Zadaj pytania diagnostyczne."


def test_a_fourth_variant_needs_no_code_change(tmp_path: Path) -> None:
    """Fourth entry added to the file → it shows up, because code names no variant."""
    own  = {**_ENTRY, "name": "eskalacja", "prompt_file": "own.md"}
    path = _variant_file(
        tmp_path,
        [_ENTRY, own],
        {"prompt_suggest_questions.md": "Pytania.", "own.md": "Eskaluj do operatora."},
    )

    variants = get_generation_variants(path)

    assert "eskalacja" in variants.names()
    assert variants.get("eskalacja").prompt == "Eskaluj do operatora."


def test_names_preserve_declaration_order(tmp_path: Path) -> None:
    """names() → same order as the file, because that is the order the buttons are drawn in."""
    second = {**_ENTRY, "name": "handoff", "prompt_file": "h.md"}
    path   = _variant_file(
        tmp_path, [_ENTRY, second], {"prompt_suggest_questions.md": "Q.", "h.md": "H."}
    )

    assert get_generation_variants(path).names() == ["questions", "handoff"]


def test_unknown_name_is_a_miss_rather_than_a_default(tmp_path: Path) -> None:
    """get() on a name nobody configured → None, so the handler can turn it into 422."""
    path = _variant_file(tmp_path, [_ENTRY], {"prompt_suggest_questions.md": "Pytania."})

    assert get_generation_variants(path).get("rozwiazanie") is None


def test_variant_without_a_prompt_document_is_rejected(tmp_path: Path) -> None:
    """Entry missing `prompt_file` → ValueError naming that key, not pydantic's `prompt`."""
    path = _variant_file(tmp_path, [{key: value for key, value in _ENTRY.items()
                                    if key != "prompt_file"}])

    with pytest.raises(ValueError, match="prompt_file"):
        get_generation_variants(path)


def test_missing_prompt_document_is_rejected(tmp_path: Path) -> None:
    """Entry pointing at a document that is not there → FileNotFoundError at load time."""
    path = _variant_file(tmp_path, [_ENTRY])   # deliberately no document written

    with pytest.raises(FileNotFoundError):
        get_generation_variants(path)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    """Two entries under one name → ValidationError, because the second would be unreachable."""
    twin = {**_ENTRY, "label": "Inny guzik", "prompt_file": "twin.md"}
    path = _variant_file(
        tmp_path, [_ENTRY, twin], {"prompt_suggest_questions.md": "Q.", "twin.md": "T."}
    )

    with pytest.raises(ValidationError, match="questions"):
        get_generation_variants(path)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    """Entry with a key we do not know → ValidationError, not a silently dropped setting."""
    path = _variant_file(
        tmp_path,
        [{**_ENTRY, "requiresHits": True}],
        {"prompt_suggest_questions.md": "Pytania."},
    )

    with pytest.raises(ValidationError):
        get_generation_variants(path)


def test_bundled_file_declares_every_field_for_every_variant() -> None:
    """Shipped default set → each entry carries name, label, requires_hits and a prompt document.

    Read as raw JSON rather than through the loader on purpose: the prompt documents themselves
    arrive in subtasks 6.3-6.5, so the shipped set is not loadable end to end yet. The test that
    loads it belongs with the last of those documents.
    """
    raw = json.loads(DEFAULT_VARIANTS_FILE.read_text(encoding="utf-8"))

    assert raw["version"] >= 1
    assert raw["variants"]

    for entry in raw["variants"]:
        assert entry["name"].strip()
        assert entry["label"].strip(),          f"{entry['name']} bez etykiety guzika"
        assert isinstance(entry["requires_hits"], bool)
        assert entry["prompt_file"].endswith(".md"), f"{entry['name']} bez dokumentu promptu"


def test_bundled_variant_names_are_unique() -> None:
    """Shipped default set → no duplicate names, so a button maps to exactly one prompt."""
    raw   = json.loads(DEFAULT_VARIANTS_FILE.read_text(encoding="utf-8"))
    names = [entry["name"] for entry in raw["variants"]]

    assert len(names) == len(set(names))
