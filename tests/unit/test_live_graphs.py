"""
Description:
Testy tej części `tests/_helpers/live/`, która nie woła modelu, a decyduje, co model
dostanie i ile razy test zapłaci: stan wejściowy sprawy, sprawy puszczane naraz (także z limitem
i czasem każdej sprawy), reguły klienta
z zestawu domyślnego po sprawdzeniu wersji i pomiar zapamiętany raz na graf. Wywołanie grafu
podmienia test. Plik stoi w korzeniu folderu, bo helper służy wszystkim grafom.
"""

import asyncio
from collections.abc import Sequence
from types import ModuleType, SimpleNamespace

import pytest

from app.agent_graphs import gate_reply, suggest_handoff
from app.agent_nodes.respond import RespondError
from app.agent_tools import AgentTool
from app.config import LLMSettings
from app.core_service.loader_dict_rules import get_rule_set
from app.engine_llm import LLMError
from tests._helpers.fake_tools import fake_agent_tools, fake_agent_tools_with_tickets
from tests._helpers.live import (
    LiveCase,
    default_rules,
    live_state,
    remember_per_graph,
    run_live_cases,
    run_timed_live_cases,
)
from tests._helpers.live import helper as live_helper
from tests._helpers.live.samples import RULES


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

    monkeypatch.setattr(live_helper, "run_live_graph", run)

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

    monkeypatch.setattr(live_helper, "run_live_graph", run)

    with pytest.raises(LLMError, match="nie odpowiedział"):
        await run_live_cases(gate_reply, None, [LiveCase("pierwsza", RULES)])


async def test_timed_live_cases_run_at_most_the_given_number_at_once_and_keep_their_order(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia wywołanie grafu
) -> None:
    """Sprawdza, czy przy limicie 2 naraz trwają najwyżej dwie sprawy z pięciu, a wyniki wracają
    w kolejności spraw.

    Wyłapuje limit, który nie działa: 120 zamknięć poszłoby do dostawcy naraz, trafiło na jego
    limit żądań, a czas sprawy w raporcie mierzyłby kolejkę u dostawcy zamiast bramki."""
    running = 0
    peak    = 0

    async def run(
        graph:      ModuleType,            # np. gate_reply
        llm:        LLMSettings,           # w teście None
        given:      Sequence[AgentTool],   # narzędzia sprawy
        input_text: str,                   # np. "sprawa 0"
        rules:      Sequence[str] | None,  # np. RULES
    ) -> str:
        nonlocal running, peak
        running += 1
        peak     = max(peak, running)

        # Kilka oddań sterowania, żeby inne sprawy zdążyły ruszyć, gdyby limit nie działał.
        for _ in range(3):
            await asyncio.sleep(0)

        running -= 1

        return f"stan {input_text}"

    monkeypatch.setattr(live_helper, "run_live_graph", run)

    cases = [LiveCase(f"sprawa {number}", RULES) for number in range(5)]
    runs  = await run_timed_live_cases(gate_reply, None, cases, concurrency=2)

    assert [run.final for run in runs] == [f"stan sprawa {number}" for number in range(5)]
    assert peak == 2


async def test_timed_live_cases_measure_each_case_without_the_wait_for_a_free_slot(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia graf i zegar
) -> None:
    """Sprawdza, czy przy jednej sprawie naraz czas każdej sprawy to tylko jej własny przebieg:
    2 i 5 sekund na zegarze testu, a nie 2 i 7.

    Wyłapuje czas liczony od wejścia do kolejki: druga sprawa doliczyłaby czekanie na pierwszą,
    a raport pokazałby czas bramki dłuższy, niż zobaczy wdrożeniowiec przy jednym zamknięciu."""
    clock = [0.0]

    async def run(
        graph:      ModuleType,            # np. gate_reply
        llm:        LLMSettings,           # w teście None
        given:      Sequence[AgentTool],   # narzędzia sprawy
        input_text: str,                   # np. "2" — ile sekund zegara testu trwa sprawa
        rules:      Sequence[str] | None,  # np. RULES
    ) -> str:
        # Oddanie sterowania w trakcie sprawy: druga sprawa staje wtedy w kolejce, zanim pierwsza
        # skończy, więc czas liczony od wejścia do kolejki wyszedłby dłuższy.
        await asyncio.sleep(0)
        clock[0] += float(input_text)

        return "stan"

    monkeypatch.setattr(live_helper, "run_live_graph", run)
    monkeypatch.setattr(live_helper, "time", SimpleNamespace(perf_counter=lambda: clock[0]))

    cases = [LiveCase("2", RULES), LiveCase("5", RULES)]
    runs  = await run_timed_live_cases(gate_reply, None, cases, concurrency=1)

    assert [run.seconds for run in runs] == [2.0, 5.0]


async def test_timed_live_cases_refuse_a_limit_below_one() -> None:
    """Sprawdza, czy limit 0 spraw naraz kończy się błędem, zanim cokolwiek ruszy.

    Wyłapuje limit, przy którym żadna sprawa nie dostałaby miejsca: przebieg wisiałby bez końca
    zamiast od razu powiedzieć, co jest nie tak."""
    with pytest.raises(ValueError, match="co najmniej 1"):
        await run_timed_live_cases(gate_reply, None, [LiveCase("pierwsza", RULES)], concurrency=0)


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
