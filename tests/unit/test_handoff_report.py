"""
Description:
Testy oceny sprawy i raportu scenariuszy przekazania sprawy (`tests/_helpers/scenarios/handoff/`),
czyli tego, na czym stoją testy układu, faktów, ostrzeżeń i dopisków na żywym modelu. Bez modelu —
tekst podaje test, a próbki leżą w `samples.py` helpera. Plik stoi w korzeniu folderu, bo ocena nie
należy do żadnego pakietu aplikacji.
"""

import dataclasses

import pytest

from app.core_model.graphs.proposal import Proposal
from tests._helpers.scenarios.handoff import (
    HandoffReport,
    judge_handoff_case,
    layout_problems,
)
from tests._helpers.scenarios.handoff.samples import sample_case, sample_clean, sample_judged


def test_a_clean_message_is_judged_as_matching() -> None:
    """Sprawdza, czy wiadomość w układzie z przykładu, z faktami i ostrzeżeniem, bez dopisków, jest
    zgodna, a pola wyniku trafiają do raportu.

    Wyłapuje ocenę, która ma fałszywy alarm na poprawnej wiadomości: każda sprawa dawałaby czerwony
    test bez winy modelu."""
    outcome = sample_judged(sample_clean())

    assert outcome.assessment     == "zgodny"
    assert outcome.fields["text"] == sample_clean()


def test_a_block_of_text_breaks_the_layout_in_every_way() -> None:
    """Sprawdza, czy jeden blok tekstu daje wszystkie cztery uwagi do układu: powitanie, pożegnanie,
    liczba akapitów i informacja o przekazaniu.

    Wyłapuje ocenę, która przepuszcza wiadomość bez akapitów, choć przykład w opisie pola każe je
    rozdzielać, i wiadomość, która w ogóle nie mówi o przekazaniu sprawy."""
    problems = layout_problems("Dzień dobry, przy wysyłce wystąpił błąd.")

    assert len(problems) == 4


@pytest.mark.parametrize(
    "handover",
    ["Sprawę przekazujemy do dalszych prac.", "Sprawa przechodzi do dalszych prac."],
)
def test_the_handover_paragraph_may_use_either_word(handover: str) -> None:
    """Sprawdza, czy informacja o przekazaniu sprawy przechodzi w obu brzmieniach, które zna ocena.

    Wyłapuje ocenę przywiązaną do jednego słowa z przykładu: poprawna wiadomość innymi słowami
    dawałaby czerwony test."""
    assert layout_problems(f"Dzień dobry.\n\nBłąd wysyłki.\n\n{handover}\n\nPozdrawiam.") == ()


def test_a_warning_in_its_own_paragraph_keeps_the_layout() -> None:
    """Sprawdza, czy wiadomość z ostrzeżeniem w osobnym akapicie, czyli z pięcioma akapitami, ma
    poprawny układ.

    Wyłapuje ocenę, która wymaga dokładnie czterech akapitów: model mógłby wydzielić ostrzeżenie,
    co jest czytelne, a test byłby czerwony."""
    text = "Dzień dobry.\n\nBłąd wysyłki.\n\nProsimy nie ponawiać.\n\nPrzekazujemy.\n\nPozdrawiam."

    assert layout_problems(text) == ()


def test_every_kind_of_finding_is_found() -> None:
    """Sprawdza, czy ocena znajduje zgubiony fakt, zgubione ostrzeżenie, liczbę spoza zgłoszenia,
    dopisek z pułapki, obietnicę, treść przykładu i przekręcony znacznik, i czy nazywa je w ocenie.

    Wyłapuje ocenę ślepą na jeden z rodzajów błędu: model mógłby zgubić ostrzeżenie albo dopisać
    termin, a test zostałby zielony."""
    text = (
        "Dzień dobry.\n\n"
        "Certyfikat jest ważny, a kod {KOD_BŁĘDU} wygasł. Sprawdzimy to w 3 dni.\n\n"
        "Przekazujemy sprawę.\n\n"
        "Pozdrawiam."
    )
    outcome = sample_judged(text)

    assert outcome.lost         == ("ePUAP", "12")
    assert outcome.warning_lost is True
    assert outcome.new_numbers  == ("3",)
    assert outcome.added        == ("wygas",)
    assert outcome.promised     == ("sprawdzimy",)
    assert outcome.copied       == ("certyfikat jest ważn",)
    assert outcome.malformed    == ("{KOD_BŁĘDU}",)
    assert outcome.assessment   == (
        "zgubione: ePUAP, 12; zgubione ostrzeżenie: nie ponawia; nowe liczby: 3; dopisane: wygas; "
        "obietnice: sprawdzimy; z przykładu: certyfikat jest ważn; "
        "przekręcone znaczniki: {KOD_BŁĘDU}"
    )


def test_any_warning_root_is_enough() -> None:
    """Sprawdza, czy wystarczy jeden rdzeń ostrzeżenia, także inny niż ten z wątku.

    Wyłapuje ocenę, która wymaga wszystkich rdzeni: model piszący „prosimy wstrzymać się z wysyłką”
    przekazałby ostrzeżenie, a test byłby czerwony."""
    text = (
        "Dzień dobry.\n\n"
        "Przy wysyłce 12 pism przez ePUAP pojawił się błąd. Prosimy wstrzymać się z wysyłką.\n\n"
        "Przekazujemy sprawę.\n\n"
        "Pozdrawiam."
    )

    assert sample_judged(text).warning_lost is False


def test_a_case_without_a_warning_cannot_lose_it() -> None:
    """Sprawdza, czy sprawa bez ostrzeżenia w wątku nie daje znaleziska o zgubionym ostrzeżeniu.

    Wyłapuje ocenę, która przy pustej liście rdzeni zgłasza brak: każda sprawa bez ostrzeżenia
    byłaby czerwona."""
    case    = dataclasses.replace(sample_case(), warning=())
    outcome = judge_handoff_case(case, Proposal(text=sample_clean(), internal_notes=""), retries=0)

    assert outcome.warning_lost is False


def test_a_rejected_answer_has_no_findings_and_no_fields() -> None:
    """Sprawdza, czy brak wyniku daje ocenę „nie do przyjęcia”, bez znalezisk i bez pól.

    Wyłapuje ocenę, która przy braku wyniku kończy się wyjątkiem albo liczy wszystkie fakty jako
    zgubione: raport nie pokazałby, co naprawdę poszło źle."""
    outcome = judge_handoff_case(sample_case(), None, retries=1)

    assert outcome.rejected     is True
    assert outcome.lost         == ()
    assert outcome.warning_lost is False
    assert outcome.fields       == {}
    assert outcome.assessment   == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_the_report_counts_cases_with_each_finding_and_prints_whole_messages() -> None:
    """Sprawdza, czy raport liczy sprawy z każdym znaleziskiem i wypisuje pod nimi każdą sprawę
    z oceną i całą wiadomością.

    Wyłapuje raport z licznikami bez treści: o przypuszczeniu podanym jako ustalenie mówi dopiero
    sama wiadomość, a wydruk jest po to, żeby ją przeczytać."""
    report = HandoffReport()
    report.record("suggest_handoff", sample_judged(sample_clean()))
    report.record("suggest_handoff", sample_judged("Dzień dobry.\n\nSprawdzimy to.\n\nPozdrawiam."))

    lines = report.lines()

    assert lines[0] == (
        "suggest_handoff: układ inny w 1 z 2, zgubione fakty w 1 z 2, zgubione ostrzeżenia "
        "w 1 z 2, dopisane w 0 z 2, obietnice w 1 z 2, z przykładu w 0 z 2, nie do przyjęcia 0"
    )
    assert any("h04 ostrzeżenie w wątku: zgodny; poprawek 0" in line for line in lines)
    assert any("Sprawdzimy to." in line for line in lines)


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport bez zgłoszonych spraw daje pustą listę linii.

    Wyłapuje nagłówek raportu drukowany w przebiegu, który tych scenariuszy nie uruchamiał."""
    assert HandoffReport().lines() == []
