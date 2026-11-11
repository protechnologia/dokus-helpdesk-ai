"""
Description:
Testy oceny sprawy i raportu scenariuszy trasy zamknięcia zgłoszenia
(`tests/_helpers/scenarios/closed/`), czyli tego, na czym stoją testy trasy `POST /tickets/closed`
na żywym modelu. Bez modelu — odpowiedź trasy podaje test, a próbki leżą w `samples.py` helpera.
"""

import pytest

from tests._helpers.scenarios.closed import ClosedReport, judge_closed_case
from tests._helpers.scenarios.closed.samples import sample_answer, sample_case


@pytest.mark.parametrize(
    ("expected", "answer", "assessment"),
    [
        ("indexed", "indexed", "zgodny"),
        ("indexed", "blocked", "ZABLOKOWANE BEZ POWODU"),
        ("indexed", "dropped", "FILTR ZDECYDOWAŁ INACZEJ"),
        ("dropped", "dropped", "zgodny"),
        ("dropped", "blocked", "ZABLOKOWANE BEZ POWODU"),
        ("dropped", "indexed", "FILTR ZDECYDOWAŁ INACZEJ"),
        ("blocked", "blocked", "zgodny"),
        ("blocked", "indexed", "PRZEPUSZCZONE PRZEZ BRAMKĘ"),
        ("blocked", "dropped", "PRZEPUSZCZONE PRZEZ BRAMKĘ"),
    ],
)
def test_an_answer_is_judged_against_the_expected_outcome(
    expected:   str,
    answer:     str,
    assessment: str,
) -> None:
    """Sprawdza, czy wynik trasy jest oceniany względem wyniku, którego wymaga sprawa: zgodny
    wynik jest zgodny, blokada zamknięcia, które miało przejść, to blokada bez powodu, karta
    z zamknięcia, które miało zostać zatrzymane, to przepuszczenie przez bramkę, a karta, która
    przeszła bramkę, ale skończyła odwrotnie w filtrze, to błąd filtra.

    Wyłapuje ocenę, która myli bramkę z filtrem albo kierunki: test blokad bez powodu liczyłby
    wtedy decyzje filtra, a test filtra — przepuszczenia bramki."""
    outcome = judge_closed_case(sample_case(expected), 200, sample_answer(answer))

    assert outcome.assessment == assessment


def test_a_route_error_is_a_failure_not_a_decision() -> None:
    """Sprawdza, czy odpowiedź trasy z kodem 503 jest oceniona jako błąd trasy z tym kodem, a nie
    jako blokada, przepuszczenie ani decyzja filtra.

    Wyłapuje ocenę, która czyta wynik z odpowiedzi błędu: awaria modelu wyglądałaby w raporcie
    jak decyzja bramki albo test padałby na brakującym polu zamiast na błędzie trasy."""
    outcome = judge_closed_case(sample_case("indexed"), 503, {"detail": "Model call failed"})

    assert outcome.failed
    assert (outcome.false_block, outcome.missed_block, outcome.wrong_filter) == (False,) * 3
    assert outcome.assessment == "BŁĄD TRASY (kod 503)"


def test_the_report_counts_errors_and_prints_every_case() -> None:
    """Sprawdza, czy raport liczy sprawy zgodne i każdy rodzaj błędu, a pod licznikami wypisuje
    każdą sprawę z oceną, kodem odpowiedzi i polami, z których widać, dlaczego tak wyszło
    (uzasadnienie karty).

    Wyłapuje raport, który gubi rodzaj błędu albo pola odpowiedzi: przy czerwonym teście nie
    dałoby się przeczytać, czy zawiniła bramka, karta czy zestaw."""
    report = ClosedReport()

    report.record(judge_closed_case(sample_case("indexed"), 200, sample_answer("indexed")))
    report.record(judge_closed_case(sample_case("blocked"), 200, sample_answer("dropped")))

    lines = report.lines()

    assert lines[0] == (
        "/tickets/closed: zgodnych 1 z 2, zablokowanych bez powodu 0, przepuszczonych przez "
        "bramkę 1, filtr inaczej 0, błędów trasy 0"
    )
    assert "    blocked zablokowane: PRZEPUSZCZONE PRZEZ BRAMKĘ; kod 200" in lines
    assert any("useful_reason: Tylko termin." in line for line in lines)


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport bez zgłoszonych spraw daje pustą listę linii.

    Wyłapuje raport, który przy przebiegu bez testów trasy wypisuje pusty nagłówek z zerami
    i zaśmieca podsumowanie pytesta."""
    assert ClosedReport().lines() == []
