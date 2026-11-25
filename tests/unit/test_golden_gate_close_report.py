"""
Description:
Ocena werdyktu, czas spraw i raport z helpera zestawu bramki zamknięcia
(`tests/_helpers/golden_gate_close/`), bez modelu. Na nich stoi test bramki na żywym modelu:
grupa wpisu mówi, jakiego werdyktu wymaga, ocena liczy fałszywe alarmy i przepuszczenia,
a raport pokazuje, które zamknięcie przeczytać. Błąd tutaj dałby fałszywy wynik pomiaru, którego
nikt by nie zauważył.
"""

import pytest

from app.core_model.graphs.verdict import Verdict
from tests._helpers.golden_gate_close import GateCloseReport, timing_summary
from tests._helpers.golden_gate_close.samples import (
    sample_block,
    sample_case,
    sample_outcome,
    sample_pass,
)


@pytest.mark.parametrize(
    ("kind", "problem", "action", "group", "expected"),
    [
        pytest.param("sprawa", True, True, "pass", "pass", id="obie reguły spełnione"),
        pytest.param("sprawa", False, True, "rule1", "block", id="nie widać problemu"),
        pytest.param("sprawa", True, False, "rule2", "block", id="nie widać, co zrobiono"),
        pytest.param("sprawa", False, False, "both", "block", id="obie reguły złamane"),
        pytest.param("powiadomienie", True, True, "notice", "block", id="powiadomienie pełne"),
        pytest.param("powiadomienie", True, False, "notice", "block", id="powiadomienie puste"),
    ],
)
def test_a_case_falls_into_the_group_its_kind_and_labels_give(
    kind:     str,   # np. "sprawa"
    problem:  bool,  # etykieta reguły 1
    action:   bool,  # etykieta reguły 2
    group:    str,   # oczekiwana grupa
    expected: str,   # oczekiwany werdykt
) -> None:
    """Sprawdza, czy sprawa trafia do grupy według złamanych reguł, a powiadomienie zawsze do
    grupy powiadomień z oczekiwaną blokadą, także gdy spełnia obie reguły.

    Wyłapuje pomyloną grupę: przepuszczenia przy regule 1 liczyłyby się jako przy regule 2,
    a powiadomienie spełniające reguły liczyłoby się jako fałszywy alarm, choć GAT-001 każe je
    blokować."""
    case = sample_case(kind=kind, problem=problem, action=action)

    assert (case.group, case.expected) == (group, expected)


@pytest.mark.parametrize(
    ("case", "verdict", "assessment"),
    [
        pytest.param(
            sample_case(), sample_block(), "FAŁSZYWY ALARM", id="dobra sprawa zablokowana",
        ),
        pytest.param(sample_case(), sample_pass(), "zgodny", id="dobra sprawa przepuszczona"),
        pytest.param(
            sample_case(action=False), sample_pass(), "PRZEPUSZCZENIE", id="bez czynności, pass",
        ),
        pytest.param(
            sample_case(action=False), sample_block(), "zgodny", id="bez czynności, block",
        ),
        pytest.param(
            sample_case(kind="powiadomienie"), sample_pass(), "PRZEPUSZCZENIE", id="powiadomienie",
        ),
        pytest.param(sample_case(), None, "ODPOWIEDŹ NIE DO PRZYJĘCIA", id="bez werdyktu"),
    ],
)
def test_a_verdict_against_the_labels_is_a_false_alarm_a_miss_or_agreement(
    case,                     # wpis zestawu
    verdict: Verdict | None,  # werdykt bramki; None — odpowiedź nie do przyjęcia
    assessment: str,          # oczekiwana ocena w raporcie
) -> None:
    """Sprawdza, czy werdykt porównany z grupą wpisu daje fałszywy alarm, przepuszczenie albo
    zgodność, a brak werdyktu nie jest ani jednym, ani drugim.

    Wyłapuje ocenę, która myli kierunki błędu (fałszywe alarmy bolą bardziej i mają osobny
    próg) albo liczy odpowiedź nie do przyjęcia jako przepuszczenie, choć helpdesk dostaje wtedy
    503 i decyduje sam."""
    outcome = sample_outcome(case, verdict)

    assert outcome.assessment == assessment
    assert not (outcome.rejected and (outcome.false_alarm or outcome.miss))


def test_a_marker_changed_by_the_model_is_malformed() -> None:
    """Sprawdza, czy odmieniony znacznik w uzasadnieniu werdyktu wychodzi jako przekręcony,
    a znacznik zapisany jak w wejściu nie.

    Wyłapuje ocenę ślepą na znaczniki: wątki korpusu niosą je w każdym zamknięciu, a odmieniony
    znacznik w uzasadnieniu nie mówi wdrożeniowcowi, o którą daną chodzi."""
    verdict = Verdict(verdict="block", reasons=["{IMIĘ} pisze, ale {NAZWISKA} nie."], hint="…")

    assert sample_outcome(sample_case(), verdict).malformed == ["{NAZWISKA}"]


def test_the_timing_summary_gives_the_median_the_nearest_rank_p90_and_the_maximum() -> None:
    """Sprawdza, czy z czasów 1–10 s podanych od końca wychodzi mediana 5,5 s, p90 9 s
    i maksimum 10 s, a z jednego czasu — on sam trzy razy.

    Wyłapuje p90 liczone z interpolacją, z przesuniętego miejsca albo bez sortowania (czasy
    przychodzą w kolejności wpisów): raport podawałby czas, którego żadne zamknięcie nie miało,
    a o cierpliwości UI helpdesku rozstrzyga właśnie ogon."""
    summary = timing_summary([float(value) for value in range(10, 0, -1)])
    single  = timing_summary([4.0])

    assert (summary.median, summary.p90, summary.maximum) == (5.5, 9.0, 10.0)
    assert (single.median, single.p90, single.maximum) == (4.0, 4.0, 4.0)


def test_the_timing_summary_refuses_an_empty_list() -> None:
    """Sprawdza, czy pusta lista czasów kończy się błędem, a nie zerami.

    Wyłapuje raport, który przy przebiegu bez spraw pokazałby czas 0 s, czyli wynik
    nieodróżnialny od bardzo szybkiej bramki."""
    with pytest.raises(ValueError, match="brak czasów"):
        timing_summary([])


def test_the_report_counts_per_group_for_doubtful_entries_and_per_stratum() -> None:
    """Sprawdza, czy raport liczy fałszywe alarmy i przepuszczenia razem, w każdej grupie, osobno
    dla wpisów wątpliwych i w każdej warstwie, bez liczników „0 z 0”.

    Wyłapuje licznik, który miesza grupy (przepuszczenie przy regule 2 widoczne jako przy regule
    1) albo gubi wpisy wątpliwe: decyzja 2026-11-25 każe je liczyć w progach, ale pokazywać
    osobno, żeby było widać, ile złych werdyktów stoi przy przypadkach granicznych."""
    report = GateCloseReport()

    report.record(sample_outcome(sample_case(ticket="90001"), sample_block()))
    report.record(sample_outcome(sample_case(ticket="90002"), sample_pass()))
    report.record(sample_outcome(
        sample_case(ticket="90003", action=False, stratum="mail", doubtful=True), sample_pass(),
    ))
    report.record(sample_outcome(sample_case(ticket="90004", kind="powiadomienie"), sample_block()))

    lines = report.lines()

    assert lines[0] == "razem: fałszywych alarmów 1 z 2, przepuszczeń 1 z 2, nie do przyjęcia 0"
    assert "    spełnia obie reguły: fałszywych alarmów 1 z 2, nie do przyjęcia 0" in lines
    assert "    łamie regułę 2: przepuszczeń 1 z 1, nie do przyjęcia 0" in lines
    assert "    powiadomienie: przepuszczeń 0 z 1, nie do przyjęcia 0" in lines
    assert "    wpisy wątpliwe: przepuszczeń 1 z 1, nie do przyjęcia 0" in lines
    assert "    warstwa mail: przepuszczeń 1 z 1, nie do przyjęcia 0" in lines
    assert not any("łamie regułę 1" in line or "łamie obie" in line for line in lines)


def test_the_report_shows_labels_and_the_verdict_only_under_a_disagreeing_closing() -> None:
    """Sprawdza, czy zamknięcie zgodne z etykietami zajmuje jedną linię, a pod niezgodnym stoją
    obie etykiety z powodem, rodzaj i pola werdyktu.

    Wyłapuje raport, w którym nie da się porównać uzasadnienia modelu z powodem etykiety, a bez
    tego nie wiadomo, czy poprawiać prompt, czy etykietę — albo raport, który zalewa wydruk
    120 werdyktami zgodnymi."""
    report = GateCloseReport()

    report.record(sample_outcome(sample_case(ticket="90001"), sample_pass(), seconds=2.5))
    report.record(sample_outcome(sample_case(ticket="90002"), sample_block(), seconds=4.0))

    lines   = report.lines()
    agreed  = lines.index("    90001 (random, spełnia obie reguły): zgodny; poprawek 0; 2,5 s")
    alarmed = lines.index(
        "    90002 (random, spełnia obie reguły): FAŁSZYWY ALARM; poprawek 0; 4,0 s",
    )

    assert agreed + 1 == alarmed
    assert lines[alarmed + 1:alarmed + 4] == [
        "        reguła 1: tak — Powód reguły 1.",
        "        reguła 2: tak — Powód reguły 2.",
        "        rodzaj: sprawa",
    ]
    assert lines[alarmed + 4:] == [
        "        verdict: block",
        '        reasons: ["Nie widać, co zrobiono."]',
        "        hint: Dopisz rozwiązanie.",
    ]


def test_the_report_adds_the_anonymization_time_to_the_gate_time() -> None:
    """Sprawdza, czy linia czasu podaje medianę, p90 i maksimum bramki, a obok medianę i maksimum
    razem z anonimizacją z pomiaru z 2026-10-19 (2,0 i 6,5 s).

    Wyłapuje czas porównywany z cierpliwością UI helpdesku bez anonimizacji: test idzie bez
    poda, więc sam czas bramki zaniżałby czas, który wdrożeniowiec odczeka przed zamknięciem."""
    report = GateCloseReport()

    for ticket, seconds in (("90001", 2.0), ("90002", 3.0), ("90003", 9.8)):
        report.record(sample_outcome(sample_case(ticket=ticket), sample_pass(), seconds=seconds))

    assert (
        "czas bramki: mediana 3,0 s, p90 9,8 s, maks. 9,8 s; z anonimizacją (pomiar 2026-10-19: "
        "mediana 2,0 s, maks. 6,5 s): mediana około 5,0 s, maks. do 16,3 s"
    ) in report.lines()


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport bez zgłoszonych zamknięć daje pustą listę.

    Wyłapuje sekcję raportu wypisywaną w każdym przebiegu pytesta, także bez żywego modelu,
    albo błąd przy liczeniu czasu z pustej listy, który zepsułby podsumowanie każdego
    przebiegu."""
    assert GateCloseReport().lines() == []
