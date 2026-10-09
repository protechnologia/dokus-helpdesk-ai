import pytest
from pydantic import ValidationError

from app.agent_tools.code.read_code_file import MAX_LINES_PER_READ, ReadCodeFileQuery

PATH = "src/lib/Urzad/Numeracja/GeneratorNumeru.php"


def test_a_path_alone_asks_for_the_whole_file() -> None:
    """Sprawdza, czy zapytanie z samą ścieżką jest poprawne i znaczy „cały plik": pierwsza linia
    to 1, a ostatniej nie ma, czyli odczyt idzie do końca pliku.

    Wyłapuje model zapytania, który wymaga numerów linii: model nie zna długości pliku przed
    pierwszym odczytem, więc małego pliku nie dałoby się przeczytać jednym wywołaniem."""
    query = ReadCodeFileQuery(path=PATH)

    assert (query.from_line, query.to_line) == (1, None)


def test_a_range_can_start_and_end_on_the_same_line() -> None:
    """Sprawdza, czy zakres z tym samym numerem na początku i na końcu, czyli jedna linia, jest
    poprawnym zapytaniem.

    Wyłapuje walidację, która wymaga co najmniej dwóch linii: model nie mógłby wtedy doczytać
    pojedynczej linii, na której urwał się poprzedni odczyt."""
    query = ReadCodeFileQuery(path=PATH, from_line=18, to_line=18)

    assert (query.from_line, query.to_line) == (18, 18)


def test_a_range_ending_before_its_start_is_refused() -> None:
    """Sprawdza, czy zakres, którego ostatnia linia ma numer mniejszy niż pierwsza, kończy się
    wyjątkiem `ValidationError` z obiema liczbami w komunikacie.

    Wyłapuje model zapytania, który przepuszcza odwrócony zakres: narzędzie oddałoby wtedy wynik
    bez linii albo z liniami, o które model nie prosił."""
    with pytest.raises(ValidationError) as caught:
        ReadCodeFileQuery(path=PATH, from_line=10, to_line=8)

    assert "10" in str(caught.value) and "8" in str(caught.value)


def test_a_range_longer_than_the_limit_is_not_refused() -> None:
    """Sprawdza, czy zakres dłuższy niż limit linii na wywołanie (`MAX_LINES_PER_READ`) jest
    poprawnym zapytaniem.

    Wyłapuje limit przeniesiony do walidacji zapytania: prośba o cały długi plik kończyłaby się
    wtedy błędem i zużytą turą, a ma dać początek pliku z informacją, że limit urwał odczyt."""
    query = ReadCodeFileQuery(path=PATH, from_line=1, to_line=MAX_LINES_PER_READ * 10)

    assert query.to_line == MAX_LINES_PER_READ * 10


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": PATH, "from_line": 0},                    # linie liczy się od 1
        {"path": PATH, "to_line": 0},                      # linie liczy się od 1
        {"path": ""},                                      # pusta ścieżka
        {"path": PATH, "offset": 120, "limit": 150},       # argumenty prototypu, nie narzędzia
    ],
    ids=["pierwsza linia zero", "ostatnia linia zero", "pusta ścieżka", "nieznane argumenty"],
)
def test_malformed_arguments_are_refused(arguments: dict) -> None:
    """Sprawdza, czy linia o numerze zero, pusta ścieżka i argumenty spoza schematu (`offset`,
    `limit`) kończą się wyjątkiem `ValidationError`.

    Wyłapuje model zapytania, który przepuszcza takie argumenty: numer zero wskazywałby linię
    przed początkiem pliku, pusta ścieżka sam katalog z kodem, a nieznany argument zostałby po
    cichu pominięty — model prosiłby o 150 linii od linii 120, a dostawał plik od początku."""
    with pytest.raises(ValidationError):
        ReadCodeFileQuery(**arguments)
