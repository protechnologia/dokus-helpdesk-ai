"""
Description:
Testy raportu zużycia żywego modelu (`LiveUsageReport` z `tests/_helpers/live/`), czyli
podsumowania, które pytest wypisuje po przebiegu testów `llm_live`. Bez modelu — zużycie jest tu
zmyślone, a próbki leżą w `samples.py` helpera. Plik stoi w korzeniu folderu, bo raport służy
testom wszystkich usług.
"""

import json

from app.agent_nodes.models import LogEntry
from tests._helpers.live import (
    CUT_MARK,
    MAX_ARGUMENTS_CHARS,
    LiveUsageReport,
    arguments_as_text,
    result_as_summary,
    run_as_lines,
)
from tests._helpers.live.samples import GATE_USAGE, RUN_LOG, RUN_MESSAGES, SEARCH_USAGE


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
    report.record("graf search", SEARCH_USAGE)
    report.record("graf gate_close", GATE_USAGE)

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
    report.record("graf search", SEARCH_USAGE, log)
    report.record("complete: zwykłe pytanie", GATE_USAGE)

    lines = report.lines()

    assert lines[0].startswith("graf search: wywołań 5, ")
    assert lines[1:3] == [
        "    agent: tura 1: narzędzia: find_code_text; 0,0041 USD",
        "    run_tools: wywołania: find_code_text; źródła: 0",
    ]
    assert lines[3].startswith("complete: zwykłe pytanie: wywołań 1, ")
    assert len(lines) == 5


def test_the_calls_of_a_turn_stand_under_that_turn_with_arguments_and_result() -> None:
    """Sprawdza, czy pod wpisem każdej tury modelu stoją wywołania narzędzi z tej właśnie tury:
    nazwa z argumentami, a linię niżej opis wyniku, który model dostał. Wpisy pozostałych węzłów
    zostają na swoich miejscach, a wywołanie bez wyniku (narzędzie odpowiedzi) ma samą linię
    z argumentami.

    Wyłapuje wywołanie przypisane do cudzej tury albo wynik do cudzego wywołania: z raportu
    czyta się, o co model pytał narzędzie i co dostał, więc przesunięcie o turę pokazywałoby
    przebieg, którego nie było."""
    assert run_as_lines(RUN_LOG, RUN_MESSAGES) == [
        "    anonymize: zanonimizowano",
        "    agent: tura 1: narzędzia: find_code_text; 0,0041 USD",
        '        find_code_text {"exact": "Brak sekwencji"}',
        "            → lines: 1, omitted_over_limit: 0",
        "    run_tools: wywołania: find_code_text; źródła: 0",
        "    agent: tura 2: narzędzia: read_code_file; 0,0038 USD",
        '        read_code_file {"path": "src/brak.php"}',
        "            → błąd: nie ma takiego pliku w kodzie aplikacji: src/brak.php",
        "    run_tools: wywołania: read_code_file; źródła: 0; błędy: 1",
        "    agent: tura 3: narzędzia: respond_search; 0,0020 USD",
        "        respond_search {}",
        "    respond: odpowiedź przyjęta",
    ]


def test_a_case_recorded_without_the_conversation_prints_the_log_alone() -> None:
    """Sprawdza, czy sprawa zgłoszona z przebiegiem, ale bez rozmowy, daje same wpisy przebiegu,
    a ta sama sprawa zgłoszona z rozmową ma pod turami modelu dodatkowe linie z wywołaniami.

    Wyłapuje raport, który bez rozmowy kończy się błędem albo gubi wpisy przebiegu: testy
    zgłaszające samo zużycie i przebieg mają działać jak dotąd."""
    without = LiveUsageReport()
    without.record("graf search", SEARCH_USAGE, RUN_LOG)

    with_talk = LiveUsageReport()
    with_talk.record("graf search", SEARCH_USAGE, RUN_LOG, RUN_MESSAGES)

    assert without.lines()[1:-1] == [f"    {entry.node}: {entry.message}" for entry in RUN_LOG]
    assert len(with_talk.lines()) == len(without.lines()) + 5


def test_the_result_is_described_by_numbers_and_flags_not_by_its_content() -> None:
    """Sprawdza opis wyniku narzędzia na wyniku odczytu pliku kodu: pola w grupach stoją pod
    pełną ścieżką, liczby i flagi z wartością (`true`, `null` jak w JSON-ie), lista linii jest
    zastąpiona liczbą pozycji, a długi tekst swoją długością. Treści linii kodu w opisie nie ma.

    Wyłapuje opis, który wkleja treść wyniku (raport po kilku odczytach miałby tysiące linii)
    albo gubi flagi zakresu: po nich widać, czy model dostał cały plik, czy odczyt urwał limit."""
    content = json.dumps({
        "path":      "src/a.php",
        "file_info": {"total_lines": 441},
        "requested": {"from_line": 1, "to_line": None},
        "returned":  {"from_line": 1, "to_line": 300, "cut_by_limit": True, "end_of_file": False},
        "lines":     [{"line": 1, "text": "<?php"}, {"line": 2, "text": "tajna_tresc();"}],
        "notes":     "x" * 200,
    })

    summary = result_as_summary(content)

    assert summary == (
        "path: src/a.php, file_info.total_lines: 441, requested.from_line: 1, "
        "requested.to_line: null, returned.from_line: 1, returned.to_line: 300, "
        "returned.cut_by_limit: true, returned.end_of_file: false, lines: 2, notes: 200 zn."
    )
    assert "tajna_tresc" not in summary


def test_long_arguments_are_cut_and_marked() -> None:
    """Sprawdza, czy argumenty dłuższe niż limit (`MAX_ARGUMENTS_CHARS`) są ucinane do limitu
    i kończą się znakiem ucięcia, a krótkie zostają w całości, z polskimi literami bez zmian.

    Wyłapuje raport, który wkleja całą propozycję z wywołania narzędzia odpowiedzi, oraz polskie
    litery zamienione na sekwencje: frazy, której szukał model, nie dałoby się przeczytać."""
    short = arguments_as_text({"exact": "Nie udało się skomunikować"})
    long  = arguments_as_text({"text": "ą" * 1000})

    assert short     == '{"exact": "Nie udało się skomunikować"}'
    assert len(long) == MAX_ARGUMENTS_CHARS + len(CUT_MARK)
    assert long.endswith(CUT_MARK)
