"""
Description:
Testy oceny golden setu anonimizatora (`tests/_helpers/golden_anonymization/`), czyli tego, na
czym stanie test ewaluacyjny silników z p. 19.4–19.5. Bez silnika — wynik anonimizacji podaje
test, a próbki leżą w `samples.py` helpera. Plik stoi w korzeniu folderu, bo ocena nie należy do
żadnego pakietu aplikacji.
"""

import pytest

from tests._helpers.golden_anonymization import (
    AnonymizationSet,
    KindCount,
    annotation_problems,
    judge_anonymization,
    measure_anonymization,
    replace_marked,
    words,
)
from tests._helpers.golden_anonymization.samples import (
    BROKEN,
    CASE,
    CLEAN,
    CODE_LOST,
    EMAIL_LEFT,
    NAME_LEFT,
    PARTIAL_PHONE,
    REAL_CASE,
    case_of,
    kinds,
    leave_the_phone_end,
)


def test_words_drop_case_polish_letters_and_punctuation() -> None:
    """Sprawdza, czy słowa do porównań to ciągi liter i cyfr małymi literami, bez polskich znaków
    (także „ł”), a interpunkcja, myślniki i nowe linie słów nie tworzą.

    Wyłapuje porównanie, w którym silnik zmieniający wielkość liter albo gubiący ogonek
    zostawiałby daną niezauważoną, a telefon zapisany z myślnikami nie pasowałby do fragmentu
    zapisanego ze spacjami."""
    assert words("Pani Annie Wiśniewskiej,\ntel. 600-123-456, Łódź") == (
        "pani", "annie", "wisniewskiej", "tel", "600", "123", "456", "lodz",
    )


def test_the_marked_replacement_is_judged_as_matching() -> None:
    """Sprawdza, czy wzorcowa zamiana zamienia każdą zaznaczoną daną na znacznik jej rodzaju,
    nie rusza reszty i wychodzi w ocenie bez przecieków i bez zniszczonej wiedzy — także gdy słowo
    telefonu („15”) zostaje w tekście jako zwykła liczba.

    Wyłapuje ocenę, która liczy jako przeciek każde słowo danej stojące gdziekolwiek w wyniku,
    i zamianę, która wycina za dużo albo za mało: test spójności zestawu przestałby wtedy
    cokolwiek sprawdzać."""
    output = replace_marked(CASE)

    assert output == CLEAN
    assert judge_anonymization(CASE, output).assessment == "zgodny"


def test_an_untouched_text_leaks_every_marked_fragment() -> None:
    """Sprawdza, czy tekst bez żadnej zmiany ma przeciek każdej zaznaczonej danej i nie ma
    zniszczonej wiedzy.

    Wyłapuje ocenę ślepą na przeciek w całości: atrapa silnika, która oddaje tekst bez zmian,
    wyszłaby w pomiarze jako anonimizator bez błędu."""
    outcome = judge_anonymization(CASE, CASE.text)

    assert outcome.leaked    == CASE.remove
    assert outcome.destroyed == ()


def test_a_word_left_from_a_fragment_is_a_leak() -> None:
    """Sprawdza, czy telefon wycięty bez ostatniej grupy cyfr liczy się jako przeciek telefonu,
    choć ta sama grupa („15”) stoi w tekście także jako zwykła liczba.

    Wyłapuje ocenę, która widzi przeciek tylko wtedy, gdy fragment stoi w wyniku w całości:
    silnik, który zostawia końcówki numerów, wyszedłby jako szczelny."""
    outcome = judge_anonymization(CASE, PARTIAL_PHONE)

    assert kinds(outcome.leaked) == ["TELEFON"]


@pytest.mark.parametrize(
    ("output", "leaked"),
    [
        pytest.param(EMAIL_LEFT, ["EMAIL"], id="adres e-mail zostawiony"),
        pytest.param(NAME_LEFT, ["IMIĘ"], id="imię zostawione"),
    ],
)
def test_a_name_inside_an_email_belongs_to_the_email(output: str, leaked: list[str]) -> None:
    """Sprawdza, czy imię i nazwisko w części lokalnej adresu e-mail należą do adresu:
    zostawiony adres to przeciek e-maila, a nie imienia i nazwiska, a zostawione imię przed
    nazwiskiem to przeciek imienia, a nie adresu.

    Wyłapuje przypisanie przecieku niewłaściwemu rodzajowi: bez NER-a (p. 19.4) każde imię
    w adresie zawyżałoby przecieki e-maili, a liczniki na rodzaj wskazywałyby nie ten silnik."""
    assert kinds(judge_anonymization(CASE, output).leaked) == leaked


def test_a_leak_in_capitals_or_without_polish_letters_is_still_a_leak() -> None:
    """Sprawdza, czy nazwisko zostawione wielkimi literami i bez polskich znaków nadal jest
    przeciekiem.

    Wyłapuje ocenę porównującą tekst znak w znak: silnik, który przepisze nazwisko inaczej, ale
    go nie usunie, wyszedłby jako szczelny."""
    case = case_of("Pozdrawiam, Anna Wiśniewska", {"NAZWISKO": ["Wiśniewska"]}, {})

    assert kinds(judge_anonymization(case, "Pozdrawiam, Anna WISNIEWSKA").leaked) == ["NAZWISKO"]


def test_knowledge_lost_in_one_of_two_places_is_destroyed() -> None:
    """Sprawdza, czy kod błędu, który w wejściu stoi dwa razy, a w wyniku raz, liczy się jako
    zniszczona wiedza.

    Wyłapuje ocenę, która pyta tylko, czy fragment jest w wyniku: silnik, który niszczy część
    wystąpień kodu błędu, po którym szuka `find_tickets_text`, wyszedłby bez strat."""
    outcome = judge_anonymization(CASE, CODE_LOST)

    assert kinds(outcome.destroyed) == ["KOD_BŁĘDU"]
    assert outcome.leaked == ()


def test_a_fragment_split_across_lines_is_found() -> None:
    """Sprawdza, czy fragment, którego słowa w tekście stoją w dwóch liniach cytatu („>”), stoi
    w tekście i daje się zamienić.

    Wyłapuje zaznaczenie, które przy danych złamanych między liniami (podpis w cytowanym mailu)
    zgłaszałoby „nie stoi w tekście” i wypadałoby z pomiaru."""
    case = case_of("> Pozdrawiam\n> Anna\n> Wiśniewska", {"NAZWISKO": ["Anna Wiśniewska"]}, {})

    assert annotation_problems(case) == ()
    assert replace_marked(case) == "> Pozdrawiam\n> {NAZWISKO}"


@pytest.mark.parametrize(("case", "problem"), BROKEN.values(), ids=BROKEN.keys())
def test_every_kind_of_wrong_marking_is_reported(case, problem: str) -> None:
    """Sprawdza, czy kontrola zaznaczeń zgłasza każdy błąd przypadku: fragment spoza tekstu,
    fragment tylko wewnątrz innego, częściowe zachodzenie danych, wiedzę na danej, brak wiedzy
    w tekście, nieznany rodzaj, fragment bez słów i powtórzenie.

    Wyłapuje kontrolę ślepą na jeden z błędów: zestaw z takim błędem dawałby pomiar, w którym
    dana nigdy nie wycieka albo wiedza nigdy nie ginie, i nikt by tego nie zauważył."""
    assert problem in annotation_problems(case)


def test_a_real_case_never_shows_its_fragments() -> None:
    """Sprawdza, czy przy przypadku z próbki korpusu ocena i kontrola zaznaczeń nazywają
    fragment rodzajem z numerem, a nie treścią.

    Wyłapuje komunikat, który cytuje daną klienta: trafiłby do konsoli i do raportu, jak
    nazwiska w wyjściu pomiaru progu (CLAUDE.md -> „Dokumentacja”)."""
    assessment = judge_anonymization(REAL_CASE, PARTIAL_PHONE).assessment
    broken     = case_of("Jan Nowak", {"IMIĘ": ["Anna"]}, {}, synthetic=False)

    assert assessment == "przecieki: TELEFON nr 1"
    assert annotation_problems(broken) == ("IMIĘ nr 1: nie stoi w tekście",)


async def test_the_measurement_counts_each_kind_present_in_the_set() -> None:
    """Sprawdza, czy pomiar liczy przecieki i zniszczoną wiedzę osobno na każdy rodzaj, który
    w zestawie stoi, i pomija rodzaje, których w nim nie ma.

    Wyłapuje licznik zbiorczy, po którym nie widać, który rodzaj przecieka, i licznik „0 z 0”,
    który wyglądałby jak rodzaj zmierzony bez błędu."""
    golden = AnonymizationSet(name="próbka", synthetic=True, cases=(CASE,))

    measurement = await measure_anonymization(golden, leave_the_phone_end)

    assert measurement.leaks == {
        "IMIĘ":     KindCount(found=0, total=1),
        "NAZWISKO": KindCount(found=0, total=1),
        "TELEFON":  KindCount(found=1, total=1),
        "EMAIL":    KindCount(found=0, total=1),
    }
    assert measurement.destroyed == {
        "KOD_BŁĘDU": KindCount(found=0, total=1),
        "NUMER":     KindCount(found=0, total=1),
    }
