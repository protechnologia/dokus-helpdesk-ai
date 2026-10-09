import pytest

from app.agent_tools.code.read_code_file import (
    MAX_LINES_PER_READ,
    ReadCodeFileQuery,
    StartOutOfFileError,
    select_lines_and_build_result,
)

# Wybieranie linii jest wspólne dla narzędzia i atrapy, więc sprawdzamy je raz, na liniach
# podanych wprost: plik to lista napisów, bez dysku. Linia numer N ma treść „linia N", więc po
# treści widać, czy numer i linia do siebie pasują.

PATH = "src/lib/Urzad/Numeracja/GeneratorNumeru.php"

# Siatka do testu zgodności flag z liczbami: długość pliku, pierwsza linia zakresu i długość
# zakresu (`None` znaczy „do końca pliku"). Układy z początkiem za końcem pliku odpadają już
# tutaj, bo to błąd, sprawdzany osobnym testem.
GRID = [
    (total, from_line, length)
    for total in (1, 14, MAX_LINES_PER_READ, MAX_LINES_PER_READ + 1, 1000)
    for from_line in (1, 2, 14, MAX_LINES_PER_READ, 700)
    for length in (None, 1, 3, MAX_LINES_PER_READ, MAX_LINES_PER_READ + 1, 5000)
    if from_line <= total
]


def _file(
    line_count: int,  # np. 14
) -> list[str]:
    """
    Description:
    Buduje linie zmyślonego pliku: linia numer N ma treść „linia N".

    Example args:
        line_count=3

    Example result:
        ["linia 1", "linia 2", "linia 3"]
    """
    return [f"linia {number}" for number in range(1, line_count + 1)]


def test_a_range_inside_the_file_comes_back_as_asked() -> None:
    """Sprawdza, czy zakres leżący w środku pliku wraca dokładnie taki, o jaki proszono: te same
    numery w zakresie żądanym i oddanym, każda linia ze swoim numerem i swoją treścią, obie flagi
    fałszywe, a długość pliku podana osobno.

    Wyłapuje numery przesunięte o jeden względem treści: model cytowałby wtedy linię sąsiednią
    do tej, którą przeczytał, i źródło wskazywałoby złe miejsce w kodzie."""
    result = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=5, to_line=7),
        PATH,
        _file(14),
    )

    assert [(line.line, line.text) for line in result.lines] == [
        (5, "linia 5"), (6, "linia 6"), (7, "linia 7"),
    ]
    assert (result.requested.from_line, result.requested.to_line) == (5, 7)
    assert (result.returned.from_line, result.returned.to_line)   == (5, 7)
    assert (result.returned.cut_by_limit, result.returned.end_of_file) == (False, False)
    assert result.file_info.total_lines == 14
    assert result.path == PATH


def test_a_whole_short_file_ends_at_the_end_of_the_file() -> None:
    """Sprawdza, czy odczyt bez zakresu pliku krótszego niż limit oddaje wszystkie linie
    i oznacza koniec pliku, a żądany koniec zakresu zostaje pusty (`None`).

    Wyłapuje odczyt całego pliku, który gubi ostatnią linię albo nie mówi, że plik się skończył:
    model próbowałby czytać dalej i dostawał błąd."""
    result = select_lines_and_build_result(ReadCodeFileQuery(path=PATH), PATH, _file(14))

    assert [line.line for line in result.lines] == list(range(1, 15))
    assert result.requested.to_line is None
    assert (result.returned.to_line, result.returned.end_of_file) == (14, True)
    assert result.returned.cut_by_limit is False


def test_a_whole_long_file_is_cut_by_the_limit() -> None:
    """Sprawdza, czy odczyt bez zakresu pliku dłuższego niż limit oddaje dokładnie tyle linii,
    ile wynosi limit (`MAX_LINES_PER_READ`), kończy się na linii o tym numerze, oznacza urwanie
    limitem i nie oznacza końca pliku.

    Wyłapuje odczyt bez limitu, który wkleja modelowi kontroler na kilka tysięcy linii, oraz
    limit bez flagi: model uznałby wtedy, że przeczytał cały plik."""
    result = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH),
        PATH,
        _file(MAX_LINES_PER_READ + 141),
    )

    assert len(result.lines)       == MAX_LINES_PER_READ
    assert result.returned.to_line == MAX_LINES_PER_READ
    assert (result.returned.cut_by_limit, result.returned.end_of_file) == (True, False)
    assert result.file_info.total_lines == MAX_LINES_PER_READ + 141


def test_asking_for_exactly_the_limit_cuts_nothing() -> None:
    """Sprawdza granicę limitu: prośba o dokładnie tyle linii, ile wynosi limit, wraca w całości
    i bez flagi urwania, a prośba o jedną linię więcej wraca urwana o tę jedną linię.

    Wyłapuje flagę ustawianą wtedy, gdy odczyt osiągnął limit, a nie wtedy, gdy czegoś zabrakło:
    model doczytywałby linie, o które nie prosił."""
    lines = _file(MAX_LINES_PER_READ * 2)

    at_the_limit = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=11, to_line=10 + MAX_LINES_PER_READ), PATH, lines,
    )
    one_more = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=11, to_line=11 + MAX_LINES_PER_READ), PATH, lines,
    )

    assert len(at_the_limit.lines) == len(one_more.lines) == MAX_LINES_PER_READ
    assert at_the_limit.returned.cut_by_limit is False
    assert one_more.returned.cut_by_limit     is True
    assert one_more.returned.to_line          == 10 + MAX_LINES_PER_READ


def test_a_range_past_the_end_of_the_file_stops_at_the_last_line() -> None:
    """Sprawdza, czy prośba o linie 12–40 pliku na 14 linii oddaje linie 12–14 i oznacza koniec
    pliku, bez flagi urwania limitem; w zakresie żądanym zostaje 40.

    Wyłapuje koniec zakresu za końcem pliku zgłaszany jako błąd (model nie zna długości pliku
    przed odczytem) oraz zakres żądany nadpisany oddanym: z wyniku nie byłoby widać, że model
    dostał mniej, niż prosił."""
    result = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=12, to_line=40),
        PATH,
        _file(14),
    )

    assert [line.line for line in result.lines] == [12, 13, 14]
    assert result.requested.to_line == 40
    assert result.returned.to_line  == 14
    assert (result.returned.cut_by_limit, result.returned.end_of_file) == (False, True)


def test_a_file_as_long_as_the_limit_is_read_whole() -> None:
    """Sprawdza, czy plik, który ma dokładnie tyle linii, ile wynosi limit, wraca w całości
    z flagą końca pliku i bez flagi urwania — także wtedy, gdy model prosił o więcej linii, niż
    plik ma.

    Wyłapuje pomylenie końca pliku z limitem tam, gdzie oba wypadają na tej samej linii: model
    próbowałby czytać dalej plik, który się skończył."""
    lines = _file(MAX_LINES_PER_READ)

    whole    = select_lines_and_build_result(ReadCodeFileQuery(path=PATH), PATH, lines)
    past_end = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=1, to_line=MAX_LINES_PER_READ + 200), PATH, lines,
    )

    for result in (whole, past_end):
        assert len(result.lines) == MAX_LINES_PER_READ
        assert (result.returned.cut_by_limit, result.returned.end_of_file) == (False, True)


def test_the_flags_always_agree_with_the_numbers() -> None:
    """Sprawdza na siatce długości pliku, początków i długości zakresu (także bez końca zakresu),
    czy flagi zawsze wynikają z liczb: koniec pliku jest oznaczony dokładnie wtedy, gdy ostatnia
    oddana linia jest ostatnią w pliku, a urwanie limitem dokładnie wtedy, gdy żądany zakres
    sięgał w pliku dalej niż oddany. Do tego linii nigdy nie jest więcej niż limit, mają kolejne
    numery od początku zakresu i obie flagi nie są prawdziwe naraz.

    Wyłapuje flagę, która przeczy zakresowi w jakimś rzadkim układzie granic: model wierzy fladze,
    więc przestałby czytać przed końcem pliku albo czytał dalej plik, który się skończył."""
    for total, from_line, length in GRID:
        # Układ granic trafia do komunikatu asercji, żeby po porażce było widać, który zawiódł.
        case    = f"plik {total} linii, od {from_line}, długość {length}"
        to_line = None if length is None else from_line + length - 1
        result  = select_lines_and_build_result(
            ReadCodeFileQuery(path=PATH, from_line=from_line, to_line=to_line),
            PATH,
            _file(total),
        )

        returned   = result.returned
        numbers    = [line.line for line in result.lines]
        wanted_end = total if to_line is None else min(to_line, total)

        assert numbers               == list(range(from_line, returned.to_line + 1)), case
        assert len(result.lines)     <= MAX_LINES_PER_READ, case
        assert returned.end_of_file  == (returned.to_line == total), case
        assert returned.cut_by_limit == (returned.to_line < wanted_end), case
        assert not (returned.cut_by_limit and returned.end_of_file), case


def test_the_text_of_a_line_comes_back_as_it_is_in_the_file() -> None:
    """Sprawdza, czy treść linii wraca znak w znak: z wcięciem na początku, ze spacjami na końcu
    i w całości, także gdy linia ma kilka tysięcy znaków.

    Wyłapuje odczyt, który zdejmuje wcięcie albo ucina długą linię, jak robi to szukanie: bez
    wcięcia nie widać, w którym bloku linia leży, a ucięta linia gubi warunek, po który model
    sięgnął do pliku."""
    long_line = "    $komunikat = '" + "bardzo długi tekst " * 300 + "';"
    lines     = ["<?php", "    if (!$sekwencja) {  ", long_line]

    result = select_lines_and_build_result(ReadCodeFileQuery(path=PATH), PATH, lines)

    assert [line.text for line in result.lines] == lines


def test_a_start_past_the_end_of_the_file_is_an_error() -> None:
    """Sprawdza, czy odczyt od linii 15 w pliku na 14 linii kończy się wyjątkiem
    `StartOutOfFileError` z długością pliku i żądanym początkiem w komunikacie, a odczyt od
    ostatniej, czternastej linii przechodzi i oddaje tę jedną linię.

    Wyłapuje pusty wynik zamiast błędu oraz granicę przesuniętą o jedną linię: wynik bez linii
    wyglądałby jak przeczytany fragment, w którym nic nie ma."""
    with pytest.raises(StartOutOfFileError) as caught:
        select_lines_and_build_result(ReadCodeFileQuery(path=PATH, from_line=15), PATH, _file(14))

    last = select_lines_and_build_result(
        ReadCodeFileQuery(path=PATH, from_line=14), PATH, _file(14),
    )

    assert caught.value.line_count == 14
    assert "14" in str(caught.value) and "15" in str(caught.value)
    assert [line.line for line in last.lines] == [14]


def test_an_empty_file_is_an_error_that_says_so() -> None:
    """Sprawdza, czy odczyt pliku bez żadnej linii kończy się wyjątkiem `StartOutOfFileError`
    z komunikatem, że plik jest pusty.

    Wyłapuje wynik z pustą listą linii oraz komunikat „plik ma 0 linii, a odczyt zaczyna się od
    linii 1", z którego model nie wyczyta, że poprawione wywołanie niczego nie zmieni."""
    with pytest.raises(StartOutOfFileError) as caught:
        select_lines_and_build_result(ReadCodeFileQuery(path=PATH), PATH, [])

    assert "pusty" in str(caught.value)
    assert PATH in str(caught.value)
