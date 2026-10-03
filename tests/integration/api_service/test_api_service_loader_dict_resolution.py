import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.model.dict_resolution_vocabulary import ResolutionVocabulary
from app.service.loader_dict_resolution import DEFAULT_DICT_FILE, get_resolution_classes


def test_bundled_vocabulary_loads() -> None:
    """Shipped default set → loads and declares at least one outcome kind."""
    vocabulary = get_resolution_classes()

    assert vocabulary.version >= 1
    assert vocabulary.classes


def test_every_class_carries_a_hint_for_the_prompt() -> None:
    """Each entry → non-empty hint (a bare identifier gets classified by guesswork)."""
    for entry in get_resolution_classes().classes:
        assert entry.hint.strip(), f"{entry.name} bez opisu dla promptu"


def test_class_names_are_unique() -> None:
    """Vocabulary → no duplicate names, so a value maps to exactly one meaning."""
    names = get_resolution_classes().names()

    assert len(names) == len(set(names))


def test_names_preserve_declaration_order() -> None:
    """names() → same order as the file, because the prompt lists them in that order."""
    raw = json.loads(DEFAULT_DICT_FILE.read_text(encoding="utf-8"))

    assert get_resolution_classes().names() == [entry["name"] for entry in raw["classes"]]


def test_vocabulary_offers_an_exit_for_an_undecided_thread() -> None:
    """Vocabulary → includes `brak`, since a thread that decides nothing is a real outcome."""
    assert "brak" in get_resolution_classes().names()


def test_vocabulary_can_be_loaded_from_another_file(tmp_path: Path) -> None:
    """Custom path → read from there (stage 8 swaps the source without touching callers)."""
    custom = tmp_path / "own_rules.json"
    custom.write_text(
        json.dumps({"version": 7, "classes": [{"name": "solved", "hint": "fixed"}]}),
        encoding="utf-8",
    )

    vocabulary = get_resolution_classes(custom)

    assert vocabulary.version == 7
    assert vocabulary.names() == ["solved"]


def test_malformed_vocabulary_is_rejected(tmp_path: Path) -> None:
    """Entry without a hint → ValidationError at load time, not a broken prompt later."""
    broken = tmp_path / "broken_rules.json"
    broken.write_text(json.dumps({"version": 1, "classes": [{"name": "solved"}]}), encoding="utf-8")

    with pytest.raises(ValidationError):
        ResolutionVocabulary.model_validate_json(broken.read_text(encoding="utf-8"))
