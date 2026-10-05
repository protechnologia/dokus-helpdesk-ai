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
    """Sprawdza, czy każda funkcja korzystająca z reguł klienta — bramka zamknięcia, bramka
    wysyłki i „Popraw" — ma zestaw domyślny, który daje się wczytać, ma numer wersji i co
    najmniej jedną regułę.

    Wyłapuje brakujący albo uszkodzony plik zestawu: taka funkcja nie miałaby reguł do
    wstawienia w prompt i nie dałaby się uruchomić."""
    rule_set = get_rule_set(graph)

    assert rule_set.version >= 1
    assert rule_set.rules


def test_an_empty_rule_set_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy plik zestawu z pustą listą reguł jest odrzucany błędem walidacji przy
    wczytaniu.

    Wyłapuje przyjęcie pustego zestawu: bramka bez reguł nie ma czego sprawdzać, a jej zgoda
    wyglądałaby jak potwierdzenie, że wszystko jest w porządku."""
    (tmp_path / "dict_rules_empty.json").write_text(json.dumps({"version": 1, "rules": []}))
    monkeypatch.setattr(loader_dict_rules, "TEXT_DIR", tmp_path)

    with pytest.raises(ValidationError):
        get_rule_set.__wrapped__("empty")


def test_the_model_rejects_a_set_without_version() -> None:
    """Sprawdza, czy zestaw reguł bez numeru wersji jest odrzucany błędem walidacji.

    Wyłapuje wersję, która stała się opcjonalna: werdykt bramki nie mógłby wtedy podać, którą
    wersją reguł został wydany, i nie dałoby się odtworzyć, dlaczego wczoraj coś przeszło,
    a dziś nie."""
    with pytest.raises(ValidationError):
        RuleSet.model_validate({"rules": ["Reguła."]})
