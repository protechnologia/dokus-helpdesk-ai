"""
Description:
Testy oceny sprawy i raportu scenariuszy „pytań już nie trzeba”
(`tests/_helpers/scenarios/questions/`), czyli tego, na czym stoją testy pytań na żywym modelu.
Bez modelu — wynik grafu podaje test. Plik stoi w korzeniu folderu, bo ocena nie należy do
żadnego pakietu aplikacji.
"""

import pytest

from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from tests._helpers.scenarios.questions import QuestionsCase, QuestionsReport, judge_questions_case

QUESTIONS = Proposal(text="1. Czy była aktualizacja?", internal_notes="1: odcina plik blokady")
NO_QUESTIONS = ProposalNotes(internal_notes="Pytań już nie trzeba: wpis z logu wskazuje 90002.")


def _case(
    questions: bool,       # np. False — fakty rozstrzygają sprawę
    case_id:   str = "w",  # np. "w01"
) -> QuestionsCase:
    """
    Description:
    Sprawa z zestawu pytań o podanym oczekiwaniu.

    Example args:
        questions=False
        case_id="w01"

    Example result:
        QuestionsCase(case_id="w01", phenomenon="rozstrzyga", text="ZGŁOSZENIE…", questions=False)
    """
    case = QuestionsCase(
        case_id    = case_id,
        phenomenon = "zawęża" if questions else "rozstrzyga",
        text       = "ZGŁOSZENIE 90701 z 2026-10-08",
        questions  = questions,
    )

    return case


@pytest.mark.parametrize(
    ("questions", "output", "assessment"),
    [
        (False, NO_QUESTIONS, "zgodny"),
        (False, QUESTIONS,    "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"),
        (True,  QUESTIONS,    "zgodny"),
        (True,  NO_QUESTIONS, "BEZ PYTAŃ, CHOĆ PRZYCZYNY KONKURUJĄ"),
    ],
)
def test_the_answer_is_judged_against_what_the_case_needs(
    questions:  bool,
    output:     Proposal | ProposalNotes,
    assessment: str,
) -> None:
    """Sprawdza, czy ocena porównuje to, czy wynik ma pytania, z tym, czego wymaga sprawa: pytania
    przy sprawie rozstrzygniętej to pytania zbędne, same uwagi przy konkurujących przyczynach to
    brak pytań, a zgodność w obie strony to „zgodny”.

    Wyłapuje ocenę, która myli kierunki — test pytań zbędnych liczyłby wtedy brak pytań —
    i taką, która pytania rozpoznaje po czymś innym niż pole `text` wyniku."""
    outcome = judge_questions_case(_case(questions), output, retries=0)

    assert outcome.assessment == assessment
    assert outcome.needless   == (assessment == "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA")
    assert outcome.missing    == (assessment == "BEZ PYTAŃ, CHOĆ PRZYCZYNY KONKURUJĄ")


@pytest.mark.parametrize("questions", [True, False])
def test_a_rejected_answer_is_neither_needless_nor_missing(questions: bool) -> None:
    """Sprawdza, czy sprawa bez wyniku — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez pól, i nie liczy się do żadnego z dwóch błędów.

    Wyłapuje ocenę, która brak wyniku dolicza do pytań zbędnych albo do braku pytań: to osobny
    rodzaj porażki, po którym wdrożeniowiec dostaje błąd."""
    outcome = judge_questions_case(_case(questions), None, retries=1)

    assert outcome.rejected
    assert not outcome.needless
    assert not outcome.missing
    assert outcome.fields     == {}
    assert outcome.assessment == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_the_report_counts_both_errors_apart_and_prints_whole_answers() -> None:
    """Sprawdza, czy raport liczy pytania zbędne wśród spraw rozstrzygniętych, brak pytań wśród
    spraw z konkurującymi przyczynami i odpowiedzi nie do przyjęcia, a pod każdą sprawą wypisuje
    pola wyniku.

    Wyłapuje raport, w którym liczniki mieszają strony, i taki, z którego nie da się przeczytać
    uwag — a tylko one mówią, które fakty wykluczyły przyczyny."""
    report = QuestionsReport()

    report.record("suggest_questions", judge_questions_case(_case(False, "w01"), QUESTIONS, 0))
    report.record("suggest_questions", judge_questions_case(_case(True, "w04"), QUESTIONS, 0))
    report.record("suggest_questions", judge_questions_case(_case(True, "w02"), None, 1))

    assert report.lines() == [
        "suggest_questions: pytania zbędne w 1 z 1, brak pytań w 0 z 2, nie do przyjęcia 1",
        "    w01 rozstrzyga: PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA; poprawek 0",
        "        text: 1. Czy była aktualizacja?",
        "        internal_notes: 1: odcina plik blokady",
        "    w04 zawęża: zgodny; poprawek 0",
        "        text: 1. Czy była aktualizacja?",
        "        internal_notes: 1: odcina plik blokady",
        "    w02 zawęża: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert QuestionsReport().lines() == []
