import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core_model.dicts.rule_set import RuleSet
from app.core_service import loader_dict_rules
from app.core_service.loader_dict_rules import get_rule_set

# Grafy, w których reguły klienta wchodzą do promptu — każdy ma wbudowany zestaw domyślny.
GRAPHS_WITH_RULES = ["gate_close", "gate_reply", "polish"]


@pytest.mark.parametrize("graph", GRAPHS_WITH_RULES)
def test_every_rule_graph_ships_a_default_set(graph: str) -> None:
    """Graf z regułami → zestaw domyślny z wersją i co najmniej jedną regułą."""
    rule_set = get_rule_set(graph)

    assert rule_set.version >= 1
    assert rule_set.rules


def test_an_empty_rule_set_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zestaw z pustą listą reguł → ValidationError: bramka bez reguł nie ma czego sprawdzać."""
    (tmp_path / "dict_rules_empty.json").write_text(json.dumps({"version": 1, "rules": []}))
    monkeypatch.setattr(loader_dict_rules, "TEXT_DIR", tmp_path)

    with pytest.raises(ValidationError):
        get_rule_set.__wrapped__("empty")


def test_the_model_rejects_a_set_without_version() -> None:
    """Zestaw bez wersji → ValidationError: werdykt musi mówić, którą wersją go wydano."""
    with pytest.raises(ValidationError):
        RuleSet.model_validate({"rules": ["Reguła."]})
