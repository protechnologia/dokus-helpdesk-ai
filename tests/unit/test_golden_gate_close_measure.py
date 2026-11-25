"""
Description:
Przebieg zestawu bramki zamknięcia (`measure_gate_close_cases()` z
`tests/_helpers/golden_gate_close/`) bez modelu: wątki z korpusu i wywołanie grafu podmienia
test. Sprawdza to, czego test na żywym modelu nie sprawdzi, bo płaci za każde wywołanie: że
etykiety pod inne reguły albo pod inny tekst zatrzymują pomiar, zanim cokolwiek trafi do modelu,
i że wynik każdej sprawy trafia do oceny, raportu i zużycia z właściwym czasem.
"""

from collections.abc import Sequence
from types import ModuleType

import pytest

from app.agent_graphs import gate_close
from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from app.core_service.loader_dict_rules import get_rule_set
from tests._helpers.golden_gate_close import (
    CONCURRENCY,
    GateCloseReport,
    measure_gate_close_cases,
    thread_digest,
)
from tests._helpers.golden_gate_close import measure as measure_module
from tests._helpers.golden_gate_close.samples import (
    sample_block,
    sample_case,
    sample_final,
)
from tests._helpers.live import LiveCase, LiveUsageReport, TimedLiveRun


@pytest.fixture
def calls(
    monkeypatch: pytest.MonkeyPatch,  # wstrzykiwane przez pytest; podmienia korpus i graf
) -> list[tuple[ModuleType, Sequence[LiveCase], int]]:
    """
    Description:
    Podmienia w pomiarze odczyt wątku z korpusu (wątek to „wątek <numer>”) i przebieg spraw na
    modelu: pierwsza sprawa dostaje blokadę po 2 s, druga odpowiedź nie do przyjęcia po 5 s.
    Oddaje listę, do której atrapa wpisuje każde wywołanie: graf, sprawy i limit naraz.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        [] — po pomiarze: [(<module gate_close>, [LiveCase(text="wątek 90001", …), …], 4)]
    """
    seen: list[tuple[ModuleType, Sequence[LiveCase], int]] = []

    async def run(
        graph:       ModuleType,          # np. gate_close
        llm:         LLMSettings,         # w teście None
        cases:       Sequence[LiveCase],  # sprawy pomiaru
        concurrency: int,                 # np. 4
    ) -> list[TimedLiveRun]:
        seen.append((graph, cases, concurrency))

        runs = [
            TimedLiveRun(final=sample_final(sample_block()), seconds=2.0),
            TimedLiveRun(final=None, seconds=5.0),
        ]

        return runs[:len(cases)]

    monkeypatch.setattr(measure_module, "closing_thread", lambda ticket, _: f"wątek {ticket}")
    monkeypatch.setattr(measure_module, "run_timed_live_cases", run)
    version = get_rule_set("gate_close").version

    monkeypatch.setattr(measure_module, "golden_gate_close_rules_version", lambda: version)

    return seen


def test_each_closing_reaches_the_graph_with_its_thread_and_the_default_rules(
    calls: list[tuple[ModuleType, Sequence[LiveCase], int]],  # wywołania atrapy przebiegu
) -> None:
    """Sprawdza, czy zamknięcia idą do grafu `gate_close` z uciętym wątkiem jako wejściem,
    z regułami z zestawu domyślnego i z limitem `CONCURRENCY` spraw naraz.

    Wyłapuje pomiar na innym grafie, z regułami z przykładu grafu zamiast tych, które bierze
    trasa, albo bez limitu: 120 zamknięć poszłoby do dostawcy naraz."""
    cases = [
        sample_case(ticket="90001", digest=thread_digest("wątek 90001")),
        sample_case(ticket="90002", digest=thread_digest("wątek 90002")),
    ]

    measure_gate_close_cases(cases, None, LiveUsageReport(), GateCloseReport())

    [(graph, live, concurrency)] = calls

    assert graph is gate_close
    assert concurrency == CONCURRENCY
    assert [case.text for case in live] == ["wątek 90001", "wątek 90002"]
    assert all(case.rules == get_rule_set("gate_close").rules for case in live)


def test_each_result_is_judged_with_its_time_and_goes_to_both_reports(
    calls: list[tuple[ModuleType, Sequence[LiveCase], int]],  # wywołania atrapy przebiegu
) -> None:
    """Sprawdza, czy sprawa z werdyktem dostaje ocenę z werdyktem i czasem 2 s i trafia do
    raportu zużycia, a sprawa bez werdyktu jest odpowiedzią nie do przyjęcia z czasem 5 s,
    bez wpisu w zużyciu; obie stoją w raporcie bramki.

    Wyłapuje czas przypisany nie tej sprawie, odpowiedź nie do przyjęcia, która przerywa pomiar
    albo liczy się jako werdykt, i raport bez którejś sprawy."""
    cases = [
        sample_case(ticket="90001", digest=thread_digest("wątek 90001")),
        sample_case(ticket="90002", digest=thread_digest("wątek 90002")),
    ]
    usage  = LiveUsageReport()
    report = GateCloseReport()

    outcomes = measure_gate_close_cases(cases, None, usage, report)

    assert [(outcome.answer, outcome.seconds) for outcome in outcomes] == [
        ("block", 2.0),
        (None, 5.0),
    ]
    assert outcomes[1].retries == MAX_RETRIES
    assert report.lines()[0] == (
        "razem: fałszywych alarmów 1 z 2, nie do przyjęcia 1"
    )
    assert sum("bramka zamknięcia: 90001" in line for line in usage.lines()) == 1
    assert not any("bramka zamknięcia: 90002" in line for line in usage.lines())


def test_a_thread_changed_since_labeling_stops_the_measurement_before_the_model(
    calls: list[tuple[ModuleType, Sequence[LiveCase], int]],  # wywołania atrapy przebiegu
) -> None:
    """Sprawdza, czy wątek, którego skrót nie zgadza się z zapisanym przy wpisie, kończy pomiar
    błędem z numerem zgłoszenia, zanim pomiar zawoła model.

    Wyłapuje pomiar bramki na tekście, którego oceniający nie widzieli (zamknięcie przez trasę
    nadpisuje wątek w korpusie): wynik byłby fałszywy, a kosztowałby jak zwykle."""
    cases = [
        sample_case(ticket="90001", digest=thread_digest("wątek 90001")),
        sample_case(ticket="90002", digest=thread_digest("inny tekst")),
    ]

    with pytest.raises(AssertionError, match="90002"):
        measure_gate_close_cases(cases, None, LiveUsageReport(), GateCloseReport())

    assert calls == []


def test_labels_written_for_other_rules_stop_the_measurement_before_the_model(
    calls:       list[tuple[ModuleType, Sequence[LiveCase], int]],  # wywołania atrapy przebiegu
    monkeypatch: pytest.MonkeyPatch,                                # podmienia wersję zestawu
) -> None:
    """Sprawdza, czy zestaw oznaczony pod inną wersję reguł niż zestaw domyślny bramki kończy
    pomiar błędem, zanim pomiar zawoła model.

    Wyłapuje pomiar po zmianie reguł klienta: etykiety mówią o regułach, których bramka już nie
    sprawdza, więc liczby nic by nie znaczyły."""
    monkeypatch.setattr(measure_module, "golden_gate_close_rules_version", lambda: 999)

    cases = [sample_case(ticket="90001", digest=thread_digest("wątek 90001"))]

    with pytest.raises(AssertionError, match="999"):
        measure_gate_close_cases(cases, None, LiveUsageReport(), GateCloseReport())

    assert calls == []
