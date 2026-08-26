import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.service.loader_variants import DEFAULT_VARIANTS_FILE, get_generation_variants

# One well-formed entry, spread out so a test can change the one field it is about.
_ENTRY = {
    "name":               "questions",
    "label":              "Jakie pytania zadać",
    "requires_hits":      False,
    "system_prompt_file": "questions_system.md",
    "user_prompt_file":   "questions_user.md",
}

# What `_variant_file` writes for a document nobody cared to spell out.
_DOCUMENTS = {"questions_system.md": "Jesteś asystentem.", "questions_user.md": "Zadaj pytania."}


def _variant_file(
    tmp_path:  Path,                          # e.g. Path("/tmp/pytest-0/test_x0")
    entries:   list[dict],                    # e.g. [{"name": "questions", …}]
    documents: dict[str, str] | None = None,  # e.g. {"questions_user.md": "Zadaj pytania."}
    version:   int = 1,
) -> Path:
    """
    Description:
    Writes a variants file plus the prompt documents its entries point at, and returns its path.
    The only axis this file has — "a variant set on disk" — so every test builds its case here
    rather than assembling JSON by hand.

    Documents land beside the variants file because that is where the loader resolves them from.
    An entry may deliberately point at a document this helper is not given, which is how the
    missing-document case is set up.

    Example args:
        tmp_path=Path("/tmp/pytest-0/test_x0")
        entries=[{"name": "questions", "system_prompt_file": "s.md", "user_prompt_file": "u.md"}]
        documents={"s.md": "Jesteś asystentem.", "u.md": "Zadaj pytania."}

    Example result:
        Path("/tmp/pytest-0/test_x0/variants.json")
    """
    documents = _DOCUMENTS if documents is None else documents

    for name, body in documents.items():
        (tmp_path / name).write_text(body, encoding="utf-8")

    path = tmp_path / "variants.json"
    path.write_text(json.dumps({"version": version, "variants": entries}), encoding="utf-8")

    return path


def test_variant_carries_the_text_of_both_prompt_documents(tmp_path: Path) -> None:
    """Entry pointing at two documents → variant's prompts are those documents' texts."""
    path = _variant_file(tmp_path, [_ENTRY])

    variant = get_generation_variants(path).get("questions")

    assert variant is not None
    assert variant.system_prompt == "Jesteś asystentem."
    assert variant.user_prompt   == "Zadaj pytania."


def test_editorial_comments_never_reach_either_prompt(tmp_path: Path) -> None:
    """Documents opening with an editorial note → the note is stripped, the instruction stays."""
    note = "<!-- DANE KLIENTA, edytowalne w runtime -->\n"
    path = _variant_file(
        tmp_path,
        [_ENTRY],
        {
            "questions_system.md": f"{note}Jesteś asystentem wdrożeniowca.",
            "questions_user.md":   f"{note}Zadaj pytania diagnostyczne.",
        },
    )

    variant = get_generation_variants(path).get("questions")

    assert "DANE KLIENTA" not in variant.system_prompt
    assert "DANE KLIENTA" not in variant.user_prompt
    assert variant.user_prompt == "Zadaj pytania diagnostyczne."


def test_a_fourth_variant_needs_no_code_change(tmp_path: Path) -> None:
    """Fourth entry added to the file → it shows up, because code names no variant."""
    own  = {**_ENTRY, "name": "eskalacja", "user_prompt_file": "own_user.md"}
    path = _variant_file(
        tmp_path, [_ENTRY, own], {**_DOCUMENTS, "own_user.md": "Eskaluj do operatora."}
    )

    variants = get_generation_variants(path)

    assert "eskalacja" in variants.names()
    assert variants.get("eskalacja").user_prompt == "Eskaluj do operatora."


def test_names_preserve_declaration_order(tmp_path: Path) -> None:
    """names() → same order as the file, because that is the order the buttons are drawn in."""
    second = {**_ENTRY, "name": "handoff"}
    path   = _variant_file(tmp_path, [_ENTRY, second])

    assert get_generation_variants(path).names() == ["questions", "handoff"]


def test_unknown_name_is_a_miss_rather_than_a_default(tmp_path: Path) -> None:
    """get() on a name nobody configured → None, so the handler can turn it into 422."""
    path = _variant_file(tmp_path, [_ENTRY])

    assert get_generation_variants(path).get("rozwiazanie") is None


@pytest.mark.parametrize("missing", ["system_prompt_file", "user_prompt_file"])
def test_variant_missing_a_prompt_document_is_rejected(tmp_path: Path, missing: str) -> None:
    """Entry missing either document reference → ValueError naming THAT key, not pydantic's."""
    entry = {key: value for key, value in _ENTRY.items() if key != missing}
    path  = _variant_file(tmp_path, [entry])

    with pytest.raises(ValueError, match=missing):
        get_generation_variants(path)


def test_missing_prompt_document_is_rejected(tmp_path: Path) -> None:
    """Entry pointing at a document that is not there → FileNotFoundError at load time."""
    path = _variant_file(tmp_path, [_ENTRY], {"questions_system.md": "Jesteś asystentem."})

    with pytest.raises(FileNotFoundError):
        get_generation_variants(path)


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    """Two entries under one name → ValidationError, because the second would be unreachable."""
    twin = {**_ENTRY, "label": "Inny guzik"}
    path = _variant_file(tmp_path, [_ENTRY, twin])

    with pytest.raises(ValidationError, match="questions"):
        get_generation_variants(path)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    """Entry with a key we do not know → ValidationError, not a silently dropped setting."""
    path = _variant_file(tmp_path, [{**_ENTRY, "requiresHits": True}])

    with pytest.raises(ValidationError):
        get_generation_variants(path)


def test_bundled_file_declares_every_field_for_every_variant() -> None:
    """Shipped default set → each entry carries name, label, requires_hits and two documents.

    Read as raw JSON rather than through the loader on purpose: the prompt documents themselves
    arrive in subtasks 6.3-6.5, so the shipped set is not loadable end to end yet. The test that
    loads it belongs with the last of those documents.
    """
    raw = json.loads(DEFAULT_VARIANTS_FILE.read_text(encoding="utf-8"))

    assert raw["version"] >= 1
    assert raw["variants"]

    for entry in raw["variants"]:
        assert entry["name"].strip()
        assert entry["label"].strip(), f"{entry['name']} bez etykiety guzika"
        assert isinstance(entry["requires_hits"], bool)
        assert entry["system_prompt_file"].endswith(".md"), f"{entry['name']}: prompt systemowy"
        assert entry["user_prompt_file"].endswith(".md"),   f"{entry['name']}: prompt użytkownika"


def test_bundled_variant_names_are_unique() -> None:
    """Shipped default set → no duplicate names, so a button maps to exactly one prompt."""
    raw   = json.loads(DEFAULT_VARIANTS_FILE.read_text(encoding="utf-8"))
    names = [entry["name"] for entry in raw["variants"]]

    assert len(names) == len(set(names))
