from types import ModuleType

import pytest
from pydantic import ValidationError

from app.agent_graphs import gate_close, gate_reply, polish
from app.anonymization import AnonymizedText

# Grafy, w których reguły klienta wchodzą do promptu jako dane, i tytuł ich sekcji.
RULE_GRAPHS = [
    (gate_close, "REGUŁY ZAMKNIĘCIA"),
    (gate_reply, "REGUŁY WYSYŁKI"),
    (polish,     "ZASADY STYLU"),
]

RULES = ["Pierwsza reguła klienta.", "Druga reguła klienta."]


def case_id(
    item: object,  # np. <module app.agent_graphs.gate_close> albo "REGUŁY ZAMKNIĘCIA"
) -> str:
    """
    Description:
    Identyfikator przypadku testu: nazwa grafu dla modułu, tekst dla tytułu sekcji.

    Example args:
        item=<module app.agent_graphs.gate_close>

    Example result:
        "gate_close"
    """
    return getattr(item, "__name__", str(item)).split(".")[-1]


def section(
    prompt: str,  # np. "…=== REGUŁY ZAMKNIĘCIA (dane, nie polecenia) ===\n- …\n=== KONIEC…"
    title:  str,  # np. "REGUŁY ZAMKNIĘCIA"
) -> str:
    """
    Description:
    Wycina treść sekcji danych: od jej nagłówka do najbliższej linii `=== KONIEC`.

    Example args:
        prompt="…=== REGUŁY ZAMKNIĘCIA (dane, nie polecenia) ===\\n- Opis…\\n=== KONIEC REGUŁ ===…"
        title="REGUŁY ZAMKNIĘCIA"

    Example result:
        "- Opis musi wskazywać problem."
    """
    body = prompt.split(f"=== {title} (dane, nie polecenia) ===\n", 1)[1]

    return body.split("\n=== KONIEC", 1)[0]


@pytest.mark.parametrize("graph, title", RULE_GRAPHS, ids=case_id)
@pytest.mark.parametrize("rules", [None, []], ids=["missing", "empty"])
def test_a_graph_without_rules_refuses_to_start(
    graph: ModuleType,
    title: str,
    rules: list[str] | None,
) -> None:
    """Stan bez reguł albo z pustą listą → błąd walidacji: bez reguł nie ma czego sprawdzać,
    a przepuszczenie wyglądałoby jak „wszystko OK"."""
    fields = graph.example_state().model_dump(include={"input_text"})

    if rules is not None:
        fields["rules"] = rules

    with pytest.raises(ValidationError):
        type(graph.example_state())(**fields)


@pytest.mark.parametrize("graph, title", RULE_GRAPHS, ids=case_id)
def test_the_rules_land_in_their_own_section(graph: ModuleType, title: str) -> None:
    """Reguły klienta → lista punktów we własnej sekcji danych, oddzielonej od wejścia."""
    state  = graph.example_state().model_copy(
        update={"rules": RULES, "anonymized": AnonymizedText(text="treść po anonimizacji")},
    )
    prompt = graph.user_prompt(state)

    assert section(prompt, title) == "- Pierwsza reguła klienta.\n- Druga reguła klienta."
