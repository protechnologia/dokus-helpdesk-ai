import json

import pytest

from app.service.loader_variants import TEXT_DIR
from app.util.markdown import read_document

# What reaches the model, editorial comments already stripped. Read straight off disk rather than
# through `get_generation_variants()`: the other variants' documents arrive in subtasks 6.4-6.5, so
# the bundled set is not loadable end to end yet.
SYSTEM = read_document(TEXT_DIR / "prompt_suggest_questions_system.md")
USER   = read_document(TEXT_DIR / "prompt_suggest_questions_user.md")

# Guards only what a diff cannot show. Unlike the parsing prompt, editing this one invalidates
# nothing on disk, so pinning phrases would buy stiffness rather than safety — whether the content
# is any good is measured on model output (subtask 6.10).


@pytest.mark.parametrize("text", [SYSTEM, USER], ids=["system", "user"])
def test_editorial_notes_never_reach_the_model(text: str) -> None:
    """Document opens with a note for us → stripped, so the model sees instructions only."""
    assert "<!--" not in text


@pytest.mark.parametrize("slot", ["{{ticket}}", "{{hits}}"])
def test_user_turn_declares_both_data_slots(slot: str) -> None:
    """Slot the service fills → present, so a deleted one cannot ship as a literal to the model."""
    assert slot in USER


def test_user_turn_carries_no_instructions() -> None:
    """User turn → data plus scaffolding only, which is what makes the split worth having.

    Guards the decision itself. Rules drifting back here would dissolve the boundary that lets
    everything in this turn be treated as someone else's content, and no diff would say so.
    """
    assert "## " not in USER

    scaffolding = USER.replace("{{ticket}}", "").replace("{{hits}}", "")

    assert len(scaffolding) < 600, "instrukcje wracają do tury użytkownika"


@pytest.mark.parametrize("text", [SYSTEM, USER], ids=["system", "user"])
def test_no_rule_stands_on_a_field_the_payload_lacks(text: str) -> None:
    """Neither document mentions `score` → `/suggest` reads payloads by id and never sees one.

    Since the 2026-08-26 decision the service fetches hits with `retrieve`, which returns no score,
    so a rule built on it would be dead text pointing at a field nobody supplies.
    """
    assert "score" not in text.lower()


def test_both_documents_are_named_by_the_variant_file() -> None:
    """Documents on disk → exactly those `variants.json` points at, so nothing is orphaned."""
    raw   = json.loads((TEXT_DIR / "variants.json").read_text(encoding="utf-8"))
    entry = next(item for item in raw["variants"] if item["name"] == "questions")

    assert {entry["system_prompt_file"], entry["user_prompt_file"]} == {
        path.name for path in TEXT_DIR.glob("prompt_suggest_questions_*.md")
    }
