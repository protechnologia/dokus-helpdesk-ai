"""
Description:
Ocena werdyktu i raport z helpera zestawu bramki wysyłki (`tests/_helpers/golden_gate_reply/`),
bez modelu. Na nich stoi test bramki na żywym modelu: łamane reguły mówią, jakiego werdyktu
wymaga wiadomość, ocena liczy fałszywe alarmy i przepuszczenia, a raport pokazuje, którą
wiadomość przeczytać. Błąd tutaj dałby fałszywy wynik pomiaru, którego nikt by nie zauważył.
"""

import pytest

from app.core_model.graphs.verdict import Verdict
from tests._helpers.golden_gate_reply import GateReplyReport
from tests._helpers.golden_gate_reply.samples import (
    sample_block,
    sample_case,
    sample_outcome,
    sample_pass,
)


@pytest.mark.parametrize(
    ("case", "verdict", "assessment"),
    [
        pytest.param(sample_case(), sample_block(), "FAŁSZYWY ALARM", id="poprawna zablokowana"),
        pytest.param(sample_case(), sample_pass(), "zgodny", id="poprawna przepuszczona"),
        pytest.param(
            sample_case(rules=(5,)), sample_pass(), "PRZEPUSZCZENIE", id="łamiąca przepuszczona",
        ),
        pytest.param(sample_case(rules=(3, 5)), sample_block(), "zgodny", id="łamiąca zablokowana"),
        pytest.param(sample_case(), None, "ODPOWIEDŹ NIE DO PRZYJĘCIA", id="bez werdyktu"),
    ],
)
def test_a_verdict_against_the_labels_is_a_false_alarm_a_miss_or_agreement(
    case,                     # wpis zestawu
    verdict: Verdict | None,  # werdykt bramki; None — odpowiedź nie do przyjęcia
    assessment: str,          # oczekiwana ocena w raporcie
) -> None:
    """Sprawdza, czy werdykt porównany z łamanymi regułami wpisu daje fałszywy alarm,
    przepuszczenie albo zgodność, a brak werdyktu nie jest ani jednym, ani drugim.

    Wyłapuje ocenę, która myli kierunki błędu (fałszywe alarmy bolą bardziej i mają osobny
    próg) albo liczy odpowiedź nie do przyjęcia jako przepuszczenie, choć helpdesk dostaje wtedy
    503 i decyduje sam."""
    outcome = sample_outcome(case, verdict)

    assert outcome.assessment == assessment
    assert not (outcome.rejected and (outcome.false_alarm or outcome.miss))


def test_a_marker_changed_by_the_model_is_malformed() -> None:
    """Sprawdza, czy odmieniony znacznik w uzasadnieniu werdyktu wychodzi jako przekręcony,
    a znacznik zapisany jak w wejściu nie, także przy przepuszczeniu bez wskazówki.

    Wyłapuje ocenę ślepą na znaczniki: wiadomości korpusu niosą je w podpisach i zwrotach,
    a odmieniony znacznik w uzasadnieniu nie mówi wdrożeniowcowi, o którą daną chodzi."""
    verdict = Verdict(verdict="block", reasons=["{IMIĘ} pisze, ale {NAZWISKA} nie."], hint="…")

    assert sample_outcome(sample_case(), verdict).malformed == ["{NAZWISKA}"]
    assert sample_outcome(sample_case(), sample_pass()).malformed == []


def test_the_report_counts_misses_per_rule_doubtful_entries_and_strata() -> None:
    """Sprawdza, czy raport liczy fałszywe alarmy i przepuszczenia razem, przepuszczenia osobno
    na każdą regułę (wiadomość łamiąca dwie reguły przy obu), osobno dla wpisów wątpliwych
    i w każdej warstwie, bez liczników „0 z 0” i bez reguł, których żadna wiadomość nie łamie.

    Wyłapuje licznik, który miesza reguły albo liczy przepuszczoną wiadomość tylko przy jednej
    z jej reguł: rzadkie reguły mają w zestawie po kilka wiadomości, więc jedna zgubiona zmienia
    obraz. Wyłapuje też zgubione wpisy wątpliwe, które decyzja 2026-11-25 każe liczyć w progach,
    ale pokazywać osobno."""
    report = GateReplyReport()

    report.record(sample_outcome(sample_case(ticket="90001"), sample_block()))
    report.record(sample_outcome(sample_case(ticket="90002"), sample_pass()))
    report.record(sample_outcome(
        sample_case(ticket="90003", rules=(3, 5), stratum="lowercase", doubtful=True),
        sample_pass(),
    ))
    report.record(sample_outcome(sample_case(ticket="90004", rules=(5,)), sample_block()))

    lines = report.lines()

    assert lines[0] == "razem: fałszywych alarmów 1 z 2, przepuszczeń 1 z 2, nie do przyjęcia 0"
    assert "    reguła 3: przepuszczeń 1 z 1" in lines
    assert "    reguła 5: przepuszczeń 1 z 2" in lines
    assert "    wpisy wątpliwe: przepuszczeń 1 z 1, nie do przyjęcia 0" in lines
    assert "    warstwa lowercase: przepuszczeń 1 z 1, nie do przyjęcia 0" in lines
    assert "    warstwa random: fałszywych alarmów 1 z 2, przepuszczeń 0 z 1, nie do przyjęcia 0" \
        in lines
    assert not any(line.startswith("    reguła 1:") for line in lines)


def test_the_report_shows_labels_and_the_verdict_only_under_a_disagreeing_message() -> None:
    """Sprawdza, czy wiadomość zgodna z etykietami zajmuje jedną linię, a pod niezgodną stoją
    łamane reguły z powodem, wątpliwość oceniającego i pola werdyktu.

    Wyłapuje raport, z którego nie da się rozstrzygnąć, czy pomyliła się bramka, czy etykieta:
    bez powodu etykiety obok uzasadnienia modelu przegląd złych werdyktów zaczyna się od zera,
    a wydruk zgodnych wiadomości w całości zasypałby te, które trzeba przeczytać."""
    report = GateReplyReport()

    report.record(sample_outcome(sample_case(ticket="90001"), sample_pass()))
    report.record(sample_outcome(
        sample_case(ticket="90002", rules=(6,), doubtful=True), sample_pass(),
    ))

    lines = report.lines()
    start = lines.index("    90001/1 (random, poprawna): zgodny; poprawek 0; 2,0 s")
    miss  = lines.index(
        "    90002/1 (random, reguły 6, wątpliwy): PRZEPUSZCZENIE; poprawek 0; 2,0 s",
    )

    assert miss == start + 1
    assert lines[miss + 1] == "        reguła 6: Powód reguły 6."
    assert lines[miss + 2] == "        wątpliwość: Wątpliwość oceniającego."
    assert any("verdict" in line and "pass" in line for line in lines[miss + 3:])


def test_the_report_adds_the_anonymization_time_to_the_gate_time() -> None:
    """Sprawdza, czy linia czasu podaje medianę, p90 i maksimum bramki, a obok czas z doliczoną
    anonimizacją krótkiego tekstu z pomiaru z 2026-10-19 (średnio 1,0 s, maks. 3,8 s).

    Wyłapuje czas bez anonimizacji albo z czasem anonimizacji długiego wątku: bramka wysyłki
    stoi przed kliknięciem „Wyślij”, więc o jej użyteczności rozstrzyga czas razem
    z anonimizacją, a wiadomość jest krótsza niż wątek."""
    report = GateReplyReport()

    for seconds in (1.0, 2.0, 4.0):
        report.record(sample_outcome(sample_case(), sample_pass(), seconds=seconds))

    assert (
        "czas bramki: mediana 2,0 s, p90 4,0 s, maks. 4,0 s; z anonimizacją (pomiar 2026-10-19, "
        "krótki tekst: średnio 1,0 s, maks. 3,8 s): mediana około 3,0 s, maks. do 7,8 s"
    ) in report.lines()


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport bez zgłoszonych wiadomości daje pustą listę.

    Wyłapuje sekcję raportu wypisaną w każdym przebiegu pytesta, także bez żywego modelu, gdzie
    pomiaru nie było."""
    assert GateReplyReport().lines() == []
