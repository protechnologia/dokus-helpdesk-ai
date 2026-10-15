"""
Description:
Testy oceny sprawy i raportu scenariuszy „Popraw” (`tests/_helpers/scenarios/polish/`), czyli
tego, na czym stoją testy słów potocznych, zgubionych faktów i dopisków na żywym modelu. Bez
modelu — tekst podaje test. Plik stoi w korzeniu folderu, bo ocena nie należy do żadnego
pakietu aplikacji.
"""

import pytest

from app.agent_graphs.polish.models import PolishedText
from tests._helpers.scenarios.polish import (
    PolishCase,
    PolishReport,
    judge_polish_case,
    numbers,
    plain,
)

CASE = PolishCase(
    case_id    = "s04",
    phenomenon = "dodatkowy krok kusi do dopisania",
    text       = "limit do epuap to 5 MB, a pdf ma 12 MB i sie wywala, bedzie cacy",
    colloquial = ("wywala", "cacy"),
    kept       = ("5 MB", "12 MB", "ePUAP"),
    tempting   = ("rozdzielczo",),
)

CLEAN = "Dzień dobry,\nlimit ePUAP to 5 MB, a plik PDF ma 12 MB.\n1. Prosimy zmniejszyć plik."


def test_plain_drops_case_polish_letters_and_spaces() -> None:
    """Sprawdza, czy zapis do porównań zdejmuje wielkie litery, polskie znaki (także „ł”)
    i odstępy.

    Wyłapuje porównanie, w którym rdzeń zapisany w notatkach bez polskich znaków nie znajduje
    tego samego słowa w poprawionym tekście, a „15MB” nie znajduje „15 MB”: słowo potoczne
    przeszłoby niezauważone, a zachowany fakt wyszedłby na zgubiony."""
    assert plain("Śmiga, Łódź i 15 MB") == "smiga,lodzi15mb"


def test_numbers_skip_list_markers_at_the_start_of_a_line() -> None:
    """Sprawdza, czy liczby w tekście to ciągi cyfr, bez numerów listy na początku linii,
    także z wcięciem i z nawiasem.

    Wyłapuje ocenę, która każdą odpowiedź z listą kroków liczy jako dopisanie liczby, choć zasady
    stylu każą kroki numerować, albo która gubi liczbę stojącą w środku zdania."""
    text = "1. Zmniejsz plik do 5 MB.\n  2) Wyślij po 3 dniach.\nWersja 4.12."

    assert numbers(text) == {"5", "3", "4", "12"}


def test_a_clean_text_is_judged_as_matching() -> None:
    """Sprawdza, czy tekst bez słów potocznych, z wszystkimi faktami, bez nowych liczb i pułapek
    jest zgodny, a pola wyniku trafiają do raportu.

    Wyłapuje ocenę, która ma fałszywy alarm na poprawnej redakcji: numer listy albo polskie znaki
    w faktach dawałyby czerwony test bez winy modelu."""
    outcome = judge_polish_case(CASE, PolishedText(text=CLEAN), retries=0)

    assert outcome.assessment == "zgodny"
    assert outcome.fields     == {"text": CLEAN}


def test_every_kind_of_change_in_content_is_found() -> None:
    """Sprawdza, czy ocena znajduje słowo potoczne zapisane z polskimi znakami, zgubiony fakt,
    liczbę spoza notatek i dopisek z pułapki, i czy nazywa je w ocenie.

    Wyłapuje ocenę ślepą na jedną z czterech zmian treści: „Popraw” mógłby zostawić potoczne
    słowo, zgubić limit albo dopisać termin i krok, a test zostałby zielony."""
    text    = "Plik się wywala. Limit ePUAP to 5 MB. Prosimy zmniejszyć rozdzielczość w 3 dni."
    outcome = judge_polish_case(CASE, PolishedText(text=text), retries=1)

    assert outcome.colloquial  == ("wywala",)
    assert outcome.lost        == ("12 MB",)
    assert outcome.new_numbers == ("3",)
    assert outcome.added       == ("rozdzielczo",)
    assert outcome.assessment  == (
        "potoczne: wywala; zgubione: 12 MB; nowe liczby: 3; dopisane: rozdzielczo"
    )


def test_a_rejected_answer_has_no_findings_and_no_fields() -> None:
    """Sprawdza, czy sprawa bez wyniku — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez znalezisk i bez pól.

    Wyłapuje ocenę, która brak tekstu liczy jako redakcję zgodną albo pada błędem, szukając słów
    w tekście, którego nie ma."""
    outcome = judge_polish_case(CASE, None, retries=1)

    assert outcome.rejected
    assert (outcome.colloquial, outcome.lost, outcome.new_numbers, outcome.added) == ((),) * 4
    assert outcome.fields     == {}
    assert outcome.assessment == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


@pytest.mark.parametrize("text", ["Wersja 10 jest gotowa.", "Poprawka w wersji 4.13."])
def test_a_number_is_new_when_its_digits_are_not_in_the_notes(text: str) -> None:
    """Sprawdza, czy liczbą nową jest ciąg cyfr, którego nie ma w notatkach, także gdy inne cyfry
    tej samej liczby w notatkach stoją.

    Wyłapuje porównanie po pojedynczych cyfrach albo po fragmencie: „10” przeszłoby, bo notatki
    mają „1” w „12”, a „4.13” — bo mają „12”."""
    case    = PolishCase("s00", "…", "wersja 4.12 z 12 MB", ("x",), (), ())
    outcome = judge_polish_case(case, PolishedText(text=text), retries=0)

    assert outcome.new_numbers in {("10",), ("13",)}


def test_the_report_counts_cases_with_each_finding_and_prints_whole_texts() -> None:
    """Sprawdza, czy raport liczy sprawy z każdym rodzajem znaleziska i odpowiedzi nie do
    przyjęcia, a pod każdą sprawą wypisuje poprawiony tekst w całości, z kolejnymi liniami
    wciętymi pod wartością.

    Wyłapuje raport, w którym liczniki mieszają rodzaje znalezisk, i taki, z którego nie da się
    przeczytać tekstu — a tylko on pokazuje krok albo obietnicę spoza list."""
    report = PolishReport()
    lost   = "Limit ePUAP to 5 MB w 2 dni."

    report.record("polish", judge_polish_case(CASE, PolishedText(text=CLEAN), retries=0))
    report.record("polish", judge_polish_case(CASE, PolishedText(text=lost), retries=0))
    report.record("polish", judge_polish_case(CASE, None, retries=1))

    assert report.lines() == [
        "polish: potoczne w 0 z 3, zgubione fakty w 1 z 3, nowe liczby w 1 z 3, "
        "dopisane w 0 z 3, nie do przyjęcia 1",
        "    s04 dodatkowy krok kusi do dopisania: zgodny; poprawek 0",
        "        text: Dzień dobry,",
        "              limit ePUAP to 5 MB, a plik PDF ma 12 MB.",
        "              1. Prosimy zmniejszyć plik.",
        "    s04 dodatkowy krok kusi do dopisania: zgubione: 12 MB; nowe liczby: 2; poprawek 0",
        "        text: Limit ePUAP to 5 MB w 2 dni.",
        "    s04 dodatkowy krok kusi do dopisania: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert PolishReport().lines() == []
