import json

import pytest

from app.service.loader_variants import TEXT_DIR
from app.util.markdown import read_document

# What reaches the model, editorial comments already stripped. Read straight off disk rather than
# through `get_generation_variants()`: the `handoff` documents arrive in subtask 6.5, so the
# bundled set is not loadable end to end yet.
SYSTEM = read_document(TEXT_DIR / "prompt_suggest_solution_system.md")
USER   = read_document(TEXT_DIR / "prompt_suggest_solution_user.md")

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


def test_only_the_user_turn_carries_data_slots() -> None:
    """System turn → no slots, because the service fills the USER document alone.

    A slot moved here would ship to the model as the literal `{{hits}}`, and the answer would look
    generated rather than failed — the kind of drift a diff of two prose documents does not show.
    """
    assert "{{" not in SYSTEM


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


def test_the_variant_guarantees_the_hits_these_documents_assume() -> None:
    """Both documents are written for at least one hit → `variants.json` must require them.

    The one guard that reaches outside the prompts, because the assumption lives outside them:
    flipping `requires_hits` to false is a one-word edit in a data file, after which the service
    would call the model with an empty hit section — and this prompt has no rule for answering
    without material, which is precisely how rule 9 gets broken quietly.
    """
    raw   = json.loads((TEXT_DIR / "variants.json").read_text(encoding="utf-8"))
    entry = next(item for item in raw["variants"] if item["name"] == "solution")

    assert entry["requires_hits"] is True


def test_both_documents_are_named_by_the_variant_file() -> None:
    """Documents on disk → exactly those `variants.json` points at, so nothing is orphaned."""
    raw   = json.loads((TEXT_DIR / "variants.json").read_text(encoding="utf-8"))
    entry = next(item for item in raw["variants"] if item["name"] == "solution")

    assert {entry["system_prompt_file"], entry["user_prompt_file"]} == {
        path.name for path in TEXT_DIR.glob("prompt_suggest_solution_*.md")
    }
