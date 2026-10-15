"""
Description:
Testy oceny sprawy i raportu scenariuszy bramek (`tests/_helpers/scenarios/gates/`), czyli
tego, na czym stoją testy fałszywych alarmów i przepuszczeń bramek na żywym modelu. Bez
modelu — werdykt podaje test. Plik stoi w korzeniu folderu, bo ocena służy wszystkim bramkom.
"""

import pytest

from app.core_model.graphs.verdict import Verdict
from tests._helpers.scenarios.gates import GateCase, GateOutcome, GateReport, judge_gate_case

BLOCK = Verdict(verdict="block", reasons=["Prośba o hasło."], hint="Usuń prośbę o hasło.")
PASS  = Verdict(verdict="pass")


def _case(
    kind: str,      # np. "trap"
    rule: int = 1,  # np. 2
) -> GateCase:
    """
    Description:
    Sprawa bramki danego rodzaju przy danej regule, z identyfikatorem złożonym z obu.

    Example args:
        kind="trap"
        rule=1

    Example result:
        GateCase(case_id="1-trap", rule=1, kind="trap", text="Dzień dobry, …")
    """
    case = GateCase(
        case_id = f"{rule}-{kind}",
        rule    = rule,
        kind    = kind,
        text    = "Dzień dobry, …",
    )

    return case


@pytest.mark.parametrize(
    ("kind", "verdict", "assessment"),
    [
        ("breaks",  BLOCK, "zgodny"),
        ("breaks",  PASS,  "PRZEPUSZCZENIE"),
        ("correct", PASS,  "zgodny"),
        ("correct", BLOCK, "FAŁSZYWY ALARM"),
        ("trap",    PASS,  "zgodny"),
        ("trap",    BLOCK, "FAŁSZYWY ALARM"),
    ],
)
def test_a_verdict_is_judged_against_the_kind_of_case(
    kind:       str,
    verdict:    Verdict,
    assessment: str,
) -> None:
    """Sprawdza, czy werdykt bramki jest oceniany według rodzaju sprawy: blokada łamiącej
    i przepuszczenie poprawnej albo pułapki są zgodne, przepuszczenie łamiącej jest
    przepuszczeniem, a blokada poprawnej albo pułapki — fałszywym alarmem.

    Wyłapuje ocenę, która myli kierunki albo traktuje pułapkę jak wiadomość łamiącą: test
    fałszywych alarmów liczyłby wtedy przepuszczenia i odwrotnie."""
    outcome = judge_gate_case(_case(kind), verdict, retries=0)

    assert outcome.assessment  == assessment
    assert outcome.false_alarm == (assessment == "FAŁSZYWY ALARM")
    assert outcome.miss        == (assessment == "PRZEPUSZCZENIE")


@pytest.mark.parametrize("kind", ["breaks", "correct", "trap"])
def test_a_rejected_answer_is_neither_a_false_alarm_nor_a_miss(kind: str) -> None:
    """Sprawdza, czy sprawa bez werdyktu — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez pól, i nie liczy się ani jako fałszywy alarm, ani jako
    przepuszczenie.

    Wyłapuje ocenę, która brak werdyktu dolicza do błędnych werdyktów: helpdesk dostaje wtedy 503
    i decyduje sam, więc to osobny rodzaj porażki, nie błędny werdykt."""
    outcome = judge_gate_case(_case(kind), None, retries=1)

    assert outcome.rejected
    assert not outcome.false_alarm
    assert not outcome.miss
    assert outcome.fields     == {}
    assert outcome.assessment == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_a_case_label_names_the_rule_and_the_kind() -> None:
    """Sprawdza, czy nazwa sprawy w raporcie podaje identyfikator, numer reguły i rodzaj po
    polsku.

    Wyłapuje raport, w którym nie widać, której reguły dotyczy fałszywy alarm, a po to bramkę
    mierzy się osobno na każdą regułę."""
    case = GateCase(case_id="g03", rule=1, kind="trap", text="…")

    assert case.label    == "g03 reguła 1, pułapka"
    assert case.expected == "pass"


def test_the_report_counts_per_gate_and_per_rule_and_prints_whole_verdicts() -> None:
    """Sprawdza, czy raport liczy fałszywe alarmy wśród spraw, które mają przejść, przepuszczenia
    wśród tych, które mają zostać zablokowane, i odpowiedzi nie do przyjęcia — dla całej bramki
    i osobno dla każdej reguły — a pod każdą sprawą wypisuje pola werdyktu.

    Wyłapuje raport, w którym liczniki mieszają kierunki albo reguły, i taki, w którym nie da się
    przeczytać uzasadnienia werdyktu, a tylko ono mówi, czy bramka zablokowała z właściwego
    powodu."""
    report = GateReport()

    report.record("gate_reply", judge_gate_case(_case("breaks", rule=1), BLOCK, retries=0))
    report.record("gate_reply", judge_gate_case(_case("trap", rule=1), BLOCK, retries=0))
    report.record("gate_reply", judge_gate_case(_case("breaks", rule=2), None, retries=1))

    assert report.lines() == [
        "gate_reply: fałszywych alarmów 1 z 1, przepuszczeń 0 z 2, nie do przyjęcia 1",
        "    reguła 1: fałszywych alarmów 1 z 1, przepuszczeń 0 z 1, nie do przyjęcia 0",
        "    reguła 2: fałszywych alarmów 0 z 0, przepuszczeń 0 z 1, nie do przyjęcia 1",
        "    1-breaks reguła 1, łamie: zgodny; poprawek 0",
        "        verdict: block",
        '        reasons: ["Prośba o hasło."]',
        "        missing: []",
        "        hint: Usuń prośbę o hasło.",
        "    1-trap reguła 1, pułapka: FAŁSZYWY ALARM; poprawek 0",
        "        verdict: block",
        '        reasons: ["Prośba o hasło."]',
        "        missing: []",
        "        hint: Usuń prośbę o hasło.",
        "    2-breaks reguła 2, łamie: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert GateReport().lines() == []


def test_an_outcome_keeps_its_case() -> None:
    """Sprawdza, czy ocena niesie sprawę, której dotyczy, razem z werdyktem i liczbą poprawek.

    Wyłapuje ocenę, która gubi sprawę albo poprawki: raport nie powiedziałby wtedy, której
    reguły dotyczy werdykt ani że model potrzebował drugiej tury."""
    case    = _case("correct", rule=3)
    outcome = judge_gate_case(case, PASS, retries=1)

    assert outcome == GateOutcome(
        case    = case,
        answer  = "pass",
        retries = 1,
        fields  = {"verdict": "pass", "reasons": [], "missing": [], "hint": ""},
    )
