import pytest

from app.core_util.text import contains_all, number_lines

LINE = "throw new Blad('Z serwerem usługi nie udało się skomunikować');"


def test_parts_may_stand_in_any_order() -> None:
    """Sprawdza, czy tekst uznaje się za zawierający wszystkie ciągi także wtedy, gdy stoją w nim
    w innej kolejności, niż je podano.

    Wyłapuje sprawdzanie, które wymaga kolejności: komunikat o innym szyku słów niż w zapytaniu
    przestałby pasować, a właśnie po to szuka się słowami zamiast frazą."""
    assert contains_all(LINE, ["skomunikować", "serwerem"], ignore_case=False)


def test_one_missing_part_is_enough_to_refuse() -> None:
    """Sprawdza, czy tekst, w którym brakuje jednego z podanych ciągów, nie jest uznawany za
    pasujący, choć pozostałe w nim są.

    Wyłapuje sprawdzanie, któremu wystarcza którykolwiek ciąg: szukanie słowami oddawałoby
    wtedy każdą linię z jednym z nich, czyli setki przypadkowych trafień."""
    assert not contains_all(LINE, ["skomunikować", "bazą"], ignore_case=False)


def test_a_part_is_a_string_of_characters_not_a_whole_word() -> None:
    """Sprawdza, czy ciąg będący początkiem dłuższego wyrazu („serwer" w „serwerem") liczy się
    jako zawarty w tekście.

    Wyłapuje dopasowanie tylko całych wyrazów: bez odmiany przez słownik rdzeń słowa jest
    jedynym sposobem, żeby trafić w jego formy."""
    assert contains_all(LINE, ["serwer", "skomunik"], ignore_case=False)


def test_case_matters_only_when_the_caller_says_so() -> None:
    """Sprawdza, czy ciągi zapisane wielkimi literami, także z polskimi znakami, pasują do tekstu
    przy `ignore_case=True`, a przy `ignore_case=False` nie pasują.

    Wyłapuje flagę, która niczego nie zmienia, oraz porównanie bez względu na wielkość liter,
    które działa tylko dla liter bez ogonków."""
    upper = ["SKOMUNIKOWAĆ", "USŁUGI"]

    assert contains_all(LINE, upper, ignore_case=True)
    assert not contains_all(LINE, upper, ignore_case=False)


def test_the_case_flag_has_no_default_and_goes_by_name() -> None:
    """Sprawdza, czy wywołanie bez `ignore_case` albo z wartością podaną bez nazwy kończy się
    błędem `TypeError`.

    Wyłapuje flagę z wartością domyślną albo przyjmowaną z pozycji: wołający, który sprawdza
    resztę warunku gdzie indziej, mógłby wtedy po cichu porównywać wielkość liter inaczej niż
    tamto miejsce."""
    with pytest.raises(TypeError):
        contains_all(LINE, ["serwerem"])  # type: ignore[call-arg]

    with pytest.raises(TypeError):
        contains_all(LINE, ["serwerem"], True)  # type: ignore[misc]


def test_each_line_gets_its_number_from_the_first_one() -> None:
    """Sprawdza, czy każda linia dostaje numer, kolejny od podanego pierwszego, z tabulatorem po
    numerze, a linie stoją w jednym tekście rozdzielone znakiem nowej linii, bez znaku na końcu.

    Wyłapuje numery liczone od zera albo od jedynki zamiast od pierwszej linii zakresu: model
    cytowałby wtedy linie przesunięte względem tych, które przeczytał."""
    assert number_lines(["    {", "        return $numer;", "    }"], first=12) == (
        "12\t    {\n13\t        return $numer;\n14\t    }"
    )


def test_the_text_of_a_line_stays_as_it_was() -> None:
    """Sprawdza, czy treść linii zostaje znak w znak: wcięcie, spacje na końcu, tabulator
    w środku, linia pusta i linia zaczynająca się od cyfr — a numer od treści oddziela zawsze
    pierwszy tabulator.

    Wyłapuje zdejmowanie wcięcia albo pustych linii: numery przestałyby odpowiadać liniom pliku,
    a bez wcięcia nie widać, w którym bloku linia leży."""
    lines = ["\tif ($a) {  ", "", "404;\t// kod", "}"]

    numbered = number_lines(lines, first=1).split("\n")

    assert [line.split("\t", 1) for line in numbered] == [
        ["1", "\tif ($a) {  "], ["2", ""], ["3", "404;\t// kod"], ["4", "}"],
    ]


def test_no_lines_give_an_empty_text() -> None:
    """Sprawdza, czy pusta lista linii daje pusty tekst.

    Wyłapuje numer bez linii („1\t") w miejscu, gdzie nie ma nic do pokazania."""
    assert number_lines([], first=1) == ""
