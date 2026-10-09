"""
Description:
Testy raportu zużycia żywego modelu (`LiveUsageReport` z `tests/helpers_live_usage.py`), czyli
podsumowania, które pytest wypisuje po przebiegu testów `llm_live`. Bez modelu — zużycie jest tu
zmyślone. Plik stoi w korzeniu folderu, bo raport służy testom wszystkich usług.
"""

from app.agent_nodes.models import LogEntry
from app.engine_llm import LLMUsage
from tests.helpers_live_usage import LiveUsageReport

SEARCH = LLMUsage(
    calls              = 5,
    prompt_tokens      = 412,
    cache_write_tokens = 8120,
    cache_read_tokens  = 25010,
    completion_tokens  = 640,
    cost_usd           = 0.0270,
)
GATE = LLMUsage(calls=1, prompt_tokens=900, completion_tokens=60, cost_usd=0.0031)


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nic nie zgłoszono, nie daje ani jednej linii.

    Wyłapuje podsumowanie wypisywane w każdym przebiegu: zwykły `pytest`, który nie woła modelu,
    kończyłby się sekcją o zużyciu z samymi zerami."""
    assert LiveUsageReport().lines() == []


def test_the_last_line_sums_every_case() -> None:
    """Sprawdza, czy ostatnia linia raportu to suma wszystkich zgłoszonych spraw: wywołań,
    tokenów w każdej z czterech klas i kosztu, zapisanego z przecinkiem.

    Wyłapuje sumę, która gubi sprawę albo klasę tokenów: po to jest ten raport, żeby po przebiegu
    na płatnym modelu od razu było widać, ile kosztował."""
    report = LiveUsageReport()
    report.record("graf search", SEARCH)
    report.record("graf gate_close", GATE)

    assert report.lines()[-1] == (
        "RAZEM: wywołań 6, świeże wejście 1312, zapis do cache 8120, odczyt z cache 25010, "
        "wyjście 700, koszt 0,0301 USD"
    )


def test_the_log_of_a_case_stands_under_its_line() -> None:
    """Sprawdza, czy wpisy przebiegu grafu stoją pod linią swojej sprawy, wcięte i w kolejności
    zgłoszenia, każdy z nazwą węzła, a sprawa bez przebiegu ma samą linię zużycia.

    Wyłapuje raport, który miesza wpisy różnych spraw albo je gubi: z przebiegu czyta się, które
    narzędzia model wołał w której turze, więc wpis pod cudzą sprawą wprowadzałby w błąd."""
    log = [
        LogEntry(node="agent",     message="tura 1: narzędzia: find_code_text; 0,0041 USD"),
        LogEntry(node="run_tools", message="wywołania: find_code_text; źródła: 0"),
    ]
    report = LiveUsageReport()
    report.record("graf search", SEARCH, log)
    report.record("complete: zwykłe pytanie", GATE)

    lines = report.lines()

    assert lines[0].startswith("graf search: wywołań 5, ")
    assert lines[1:3] == [
        "    agent: tura 1: narzędzia: find_code_text; 0,0041 USD",
        "    run_tools: wywołania: find_code_text; źródła: 0",
    ]
    assert lines[3].startswith("complete: zwykłe pytanie: wywołań 1, ")
    assert len(lines) == 5
