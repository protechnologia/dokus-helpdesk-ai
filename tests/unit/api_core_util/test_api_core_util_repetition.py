"""
Description:
Usuwanie powtórzonych linii z `core_util/repetition.py`: na nim stoi czyszczenie wątków kanału
„Automat mailowy” (p. 32). Przykłady to przykłady z notatki o metodzie: mail i odpowiedź, która
go cytuje, z ciągiem 12 słów jak w normalizerze.
"""

from app.core_util.repetition import (
    remove_repeated_lines,
    run_digest,
    run_digests,
    words_of,
)
from tests._helpers.mail.samples import (
    sample_doubled_mail,
    sample_quote,
    sample_quote_with_new_word,
    sample_quote_without_extra_word,
    sample_quote_without_polish_letters,
    sample_reflowed_quote,
)

# Długość powtórzonego ciągu jak w słowniku maili.
RUN_WORDS = 12


def test_a_quote_of_an_earlier_mail_disappears() -> None:
    """Sprawdza, czy z odpowiedzi znika cytat wcześniejszego maila, także jego krótka pierwsza
    linia („Co tam słychać?”), a nowa treść zostaje.

    Wyłapuje cytat zostawiony w odpowiedzi: model czytałby tę samą wiadomość dwa razy,
    a anonimizator dostawałby kilka razy dłuższy tekst z tymi samymi nazwiskami."""
    mail, reply, expected = sample_quote()

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set()) == [mail, expected]


def test_punctuation_case_and_line_breaks_do_not_matter() -> None:
    """Sprawdza, czy cytat złamany w innym miejscu, małymi literami, z myślnikiem zamiast
    dwukropka i bez cudzysłowów znika tak samo jak dosłowny.

    Wyłapuje porównanie znak w znak albo linia w linię: programy pocztowe łamią cytat po
    swojemu, więc większość cytatów zostałaby w wątku."""
    mail, reply = sample_reflowed_quote()

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set()) == [mail, ""]


def test_a_new_word_keeps_its_line_and_the_rest_of_the_quote_disappears() -> None:
    """Sprawdza, czy w cytacie z dopisanym „nadal” zostają dwie pierwsze linie (przed „nadal”
    stoi tylko 10 słów ciągu, a druga linia niesie nowe słowo), a trzecia, za którą ciąg ma
    15 słów, znika.

    Wyłapuje usuwanie linii, w której stoi nowe słowo: odpowiedź wpisana w linię cytatu
    zniknęłaby razem z nim. Wyłapuje też powtórzenie liczone od mniej niż 12 słów."""
    mail, reply, expected = sample_quote_with_new_word()

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set())[1] == expected


def test_an_extra_word_in_the_original_changes_nothing() -> None:
    """Sprawdza, czy cytat bez słowa „Niestety”, od którego zaczynał się oryginał, znika cały.

    Wyłapuje porównanie, które wymaga, żeby cytat zaczynał się tam, gdzie oryginał: cytat
    urwany o jedno słowo zostałby w wątku."""
    mail, reply = sample_quote_without_extra_word()

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set())[1] == ""


def test_letters_without_polish_diacritics_are_different_words() -> None:
    """Sprawdza, czy cytat 13 słów napisany bez polskich znaków („mozemy”, „urzedu”) zostaje.

    Wyłapuje zrównanie liter z ogonkami i bez nich: ten sam tekst bez ogonków bywa nową
    wiadomością pisaną na szybko, a nie kopią."""
    mail, reply = sample_quote_without_polish_letters()

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set())[1] == reply


def test_a_repetition_shorter_than_the_run_stays() -> None:
    """Sprawdza, czy linia powtarzająca krótszy ciąg niż 12 słów (zwrot, krótkie pytanie)
    zostaje.

    Wyłapuje zbyt krótki ciąg: wtedy z nowych wiadomości znikałyby zwroty i krótkie zdania,
    które powtarzają się w każdej korespondencji."""
    texts = ["Nie działa wysyłka pism.", "> Nie działa wysyłka pism.\nSprawdzimy to dziś."]

    assert remove_repeated_lines(texts, RUN_WORDS, set()) == texts


def test_the_second_copy_of_a_mail_in_one_text_disappears() -> None:
    """Sprawdza, czy z tekstu, w którym mail stoi dwa razy (druga kopia złamana inaczej),
    zostaje pierwsza kopia.

    Wyłapuje szukanie powtórzeń tylko w poprzednich tekstach: w kanale mailowym opis niesie
    mail dwa razy (wersja HTML i zwykły tekst), więc druga kopia zostałaby w każdym opisie."""
    doubled, first = sample_doubled_mail()

    assert remove_repeated_lines([doubled], RUN_WORDS, set()) == [first]


def test_a_known_fragment_disappears_at_its_first_occurrence() -> None:
    """Sprawdza, czy linie znanego fragmentu (skrót na liście znanych) znikają w pierwszym
    tekście, w którym fragment się pojawia, a bez listy zostają.

    Wyłapuje listę znanych fragmentów, która nie działa przy pierwszym wystąpieniu: stopka
    i klauzula RODO z pierwszej wiadomości zostawałyby w każdym wątku."""
    footer = (
        "Ta wiadomość i jej załączniki są poufne i przeznaczone\n"
        "wyłącznie dla wskazanego odbiorcy."
    )
    text  = f"Proszę ponowić wysyłkę.\n{footer}"
    known = run_digests(footer, RUN_WORDS)

    assert remove_repeated_lines([text], RUN_WORDS, known) == ["Proszę ponowić wysyłkę."]
    assert remove_repeated_lines([text], RUN_WORDS, set()) == [text]


def test_lines_without_words_stay_and_blank_lines_collapse() -> None:
    """Sprawdza, czy po wycięciu cytatu linia bez słów („> ”) zostaje, a kilka pustych linii
    pod rząd zwija się do jednej.

    Wyłapuje usuwanie linii bez słów (z pustymi liniami znikałby podział na akapity) i dziury
    po wyciętych liniach, które rozciągałyby wątek pustymi wierszami."""
    mail  = "Od wczoraj nie możemy wysłać żadnego pisma do ePUAP. Prosimy o pomoc."
    reply = f"Odpowiedź.\n\n> {mail}\n\n\n> \n\nPozdrawiam"

    assert remove_repeated_lines([mail, reply], RUN_WORDS, set())[1] == (
        "Odpowiedź.\n\n> \n\nPozdrawiam"
    )


def test_the_digest_of_a_run_keeps_its_golden_value() -> None:
    """Sprawdza, czy skrót znanego ciągu 12 słów ma zapisaną wartość, a słowa wchodzą do niego
    małymi literami, bez interpunkcji.

    Wyłapuje zmianę sposobu liczenia skrótu: słownik szablonów zbudowany starym sposobem
    przestałby po cichu działać, bo żaden skrót by się z nim nie zgadzał."""
    text  = "Ta wiadomość i jej załączniki są poufne\ni przeznaczone, wyłącznie DLA wskazanego"
    words = words_of(text)

    assert run_digest(words) == "5705455ac3eda8f5"


def test_run_digests_cover_every_window_once() -> None:
    """Sprawdza, czy tekst z 13 słów daje skróty dwóch okien po 12 słów, tekst powtarzający
    to samo okno — jeden skrót, a tekst krótszy niż okno — żadnego.

    Wyłapuje pominięte okno na brzegu tekstu (fragment na końcu stopki nie trafiłby do
    słownika) i okno liczone wielokrotnie."""
    thirteen = " ".join(f"słowo{number}" for number in range(13))
    repeated = " ".join(["jedno"] * 14)

    assert len(run_digests(thirteen, RUN_WORDS)) == 2
    assert len(run_digests(repeated, RUN_WORDS)) == 1
    assert run_digests("za krótki tekst", RUN_WORDS) == set()
