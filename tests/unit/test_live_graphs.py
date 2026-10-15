"""
Description:
Testy tej części `tests/helpers_live_graphs.py`, która nie woła modelu, a decyduje, co model
dostanie i ile razy test zapłaci: stan wejściowy sprawy, sprawy puszczane naraz, reguły klienta
z zestawu domyślnego po sprawdzeniu wersji i pomiar zapamiętany raz na graf. Wywołanie grafu
podmienia test. Plik stoi w korzeniu folderu, bo helper służy wszystkim grafom.
"""

from collections.abc import Sequence
from types import ModuleType

import pytest

from app.agent_graphs import gate_reply, suggest_handoff
from app.agent_nodes.respond import RespondError
from app.agent_tools import AgentTool
from app.config import LLMSettings
from app.core_service.loader_dict_rules import get_rule_set
from app.engine_llm import LLMError
from tests import helpers_live_graphs
from tests.helpers_agent_tools import fake_agent_tools, fake_agent_tools_with_tickets
from tests.helpers_live_graphs import (
    LiveCase,
    default_rules,
    live_state,
    remember_per_graph,
    run_live_cases,
)

RULES = ["Wiadomość nie prosi klienta o hasło ani login."]


def test_a_live_state_takes_the_given_input_and_rules() -> None:
    """Sprawdza, czy stan sprawy niesie podane wejście i reguły klienta, a bez nich — wejście
    i reguły ze stanu przykładowego grafu.

    Wyłapuje sprawę bramki sprawdzaną regułami z przykładu zamiast podanych (atak w regułach nie
    dotarłby do modelu) i wejście, które nie zastępuje przykładowego."""
    given   = live_state(gate_reply, "Dzień dobry, …", RULES)
    example = live_state(gate_reply)

    assert (given.input_text, given.rules) == ("Dzień dobry, …", RULES)
    assert example == gate_reply.example_state()
    assert live_state(suggest_handoff, "ZGŁOSZENIE 1").input_text == "ZGŁOSZENIE 1"


async def test_live_cases_keep_their_order_rules_and_tools_and_a_rejected_answer_is_none(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia wywołanie grafu
) -> None:
    """Sprawdza, czy sprawy idą do grafu z własnymi regułami i narzędziami (bez podanych — z
    atrapami wszystkich narzędzi), wyniki wracają w kolejności spraw, a sprawa, której
    odpowiedzi węzeł `respond` nie przyjął, daje `None`.

    Wyłapuje reguły albo narzędzia z materiałem ataku gubione po drodze do grafu — atak w karcie
    nie dotarłby wtedy do modelu — wyniki przypisane nie tym sprawom i odpowiedź nie do
    przyjęcia, która przerywa cały przebieg zamiast zostać oceniona."""
    seen:  list[tuple[str, Sequence[str] | None]] = []
    tools: list[Sequence[AgentTool]] = []
    own   = fake_agent_tools_with_tickets(cards=[], threads=None)

    async def run(
        graph:      ModuleType,            # np. gate_reply
        llm:        LLMSettings,           # w teście None
        given:      Sequence[AgentTool],   # narzędzia sprawy
        input_text: str,                   # np. "pierwsza"
        rules:      Sequence[str] | None,  # np. RULES
    ) -> str:
        seen.append((input_text, rules))
        tools.append(given)

        # --- sprawa, której odpowiedzi węzeł `respond` nie przyjął ---
        if input_text == "odrzucona":
            raise RespondError("respond_gate_reply: odpowiedź nie do przyjęcia")

        return f"stan {input_text}"

    monkeypatch.setattr(helpers_live_graphs, "run_live_graph", run)

    cases  = [LiveCase("pierwsza", RULES, own), LiveCase("odrzucona")]
    finals = await run_live_cases(gate_reply, None, cases)

    assert finals == ["stan pierwsza", None]
    assert seen   == [("pierwsza", RULES), ("odrzucona", None)]
    assert tools[0] is own
    assert [tool.name for tool in tools[1]] == [tool.name for tool in fake_agent_tools()]


async def test_live_cases_let_other_model_errors_through(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia wywołanie grafu
) -> None:
    """Sprawdza, czy błąd modelu inny niż odpowiedź nie do przyjęcia przerywa przebieg spraw.

    Wyłapuje awarię dostawcy liczoną jako odpowiedź nie do przyjęcia: scenariusz zapisałby
    przebicie albo brak werdyktu, choć model w ogóle nie odpowiedział."""

    async def run(*_: object) -> str:
        raise LLMError("dostawca nie odpowiedział")

    monkeypatch.setattr(helpers_live_graphs, "run_live_graph", run)

    with pytest.raises(LLMError, match="nie odpowiedział"):
        await run_live_cases(gate_reply, None, [LiveCase("pierwsza", RULES)])


def test_default_rules_are_the_rule_set_of_the_graph_in_the_expected_version() -> None:
    """Sprawdza, czy scenariusz pod wersję zestawu domyślnego dostaje reguły z tego zestawu,
    a scenariusz bez wersji — brak reguł.

    Wyłapuje scenariusz bramki sprawdzany innymi regułami niż te, które bierze trasa, i graf bez
    reguł, któremu test podmieniłby stan."""
    rule_set = get_rule_set("gate_reply")

    assert default_rules("gate_reply", rule_set.version) == rule_set.rules
    assert default_rules("suggest_handoff", None) is None


def test_default_rules_refuse_another_version() -> None:
    """Sprawdza, czy scenariusz napisany pod inną wersję reguł kończy się błędem, który podaje
    obie wersje.

    Wyłapuje sprawy napisane pod reguły, których już nie ma: bez błędu test zapłaciłby za pomiar,
    który nic nie mierzy."""
    version = get_rule_set("gate_reply").version

    with pytest.raises(AssertionError, match=f"wersji {version + 1}.*wersję {version}"):
        default_rules("gate_reply", version + 1)


def test_a_measurement_runs_once_per_graph() -> None:
    """Sprawdza, czy pomiar grafu jest wołany raz, a kolejne prośby o ten graf dostają ten sam
    wynik, i czy inny graf ma własny pomiar.

    Wyłapuje pomiar powtarzany w każdym teście grafu: każdy test płaciłby za te same sprawy od
    nowa."""
    calls: list[str] = []

    def measure(name: str) -> str:
        calls.append(name)

        return f"wynik {name}"

    run = remember_per_graph(measure)

    assert run("gate_reply") == "wynik gate_reply"
    assert run("gate_reply") == "wynik gate_reply"
    assert run("parse_ticket") == "wynik parse_ticket"
    assert calls == ["gate_reply", "parse_ticket"]


def test_a_failed_measurement_is_remembered_with_its_error() -> None:
    """Sprawdza, czy pomiar zakończony błędem jest zapamiętany razem z błędem: kolejna prośba
    o ten graf dostaje ten sam błąd bez ponownego pomiaru.

    Wyłapuje nieudany pomiar opłacany od nowa w każdym teście grafu, na przykład przy awarii
    dostawcy w połowie spraw."""
    calls: list[str] = []

    def measure(name: str) -> str:
        calls.append(name)

        raise RuntimeError(f"awaria {name}")

    run = remember_per_graph(measure)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="awaria gate_reply"):
            run("gate_reply")

    assert calls == ["gate_reply"]
