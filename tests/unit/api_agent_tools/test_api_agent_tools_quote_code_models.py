import pytest
from pydantic import ValidationError

from app.agent_tools.code.quote_code import MAX_LINES_PER_QUOTE, QuoteCodeQuery

PATH = "src/lib/Urzad/Numeracja/GeneratorNumeru.php"


def test_a_quote_without_a_role_is_refused() -> None:
    """Sprawdza, czy cytowanie bez roli kończy się wyjątkiem `ValidationError`.

    Wyłapuje rolę z wartością domyślną: od roli zależy, czy fragment trafi na listę źródeł
    odpowiedzi, więc model ma ją podać świadomie, a nie dostać „przyczynę" za samo wywołanie."""
    with pytest.raises(ValidationError):
        QuoteCodeQuery(path=PATH, from_line=8, to_line=10)


def test_a_role_outside_the_two_known_is_refused() -> None:
    """Sprawdza, czy rola inna niż `cause` i `excluded` (tu `related`) kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje model, który przyjmuje dowolną rolę: narzędzie robi źródło tylko z roli `cause`, więc
    cytowanie z rolą wymyśloną przez model przeszłoby bez błędu i bez źródła."""
    with pytest.raises(ValidationError):
        QuoteCodeQuery(path=PATH, from_line=8, to_line=10, role="related")


def test_a_fragment_ending_before_its_start_is_refused() -> None:
    """Sprawdza, czy fragment, którego ostatnia linia ma numer mniejszy niż pierwsza, kończy się
    wyjątkiem `ValidationError` z obiema liczbami w komunikacie.

    Wyłapuje model, który przepuszcza odwrócony zakres: powstałoby z niego źródło z zakresem linii,
    którego nie da się otworzyć w pliku."""
    with pytest.raises(ValidationError) as caught:
        QuoteCodeQuery(path=PATH, from_line=10, to_line=8, role="cause")

    assert "10" in str(caught.value) and "8" in str(caught.value)


def test_a_fragment_over_the_limit_is_refused_and_one_at_the_limit_is_not() -> None:
    """Sprawdza, czy fragment o jedną linię dłuższy niż limit (`MAX_LINES_PER_QUOTE`) kończy się
    wyjątkiem `ValidationError`, a fragment dokładnie na limicie przechodzi.

    Wyłapuje brak górnej granicy albo granicę przesuniętą o jeden: bez limitu model cytowałby całe
    metody i pliki, a źródłem ma być miejsce, które rozstrzyga."""
    with pytest.raises(ValidationError):
        QuoteCodeQuery(path=PATH, from_line=1, to_line=MAX_LINES_PER_QUOTE + 1, role="cause")

    at_the_limit = QuoteCodeQuery(path=PATH, from_line=1, to_line=MAX_LINES_PER_QUOTE, role="cause")

    assert at_the_limit.to_line == MAX_LINES_PER_QUOTE


def test_one_line_is_a_fragment() -> None:
    """Sprawdza, czy fragment z jednej linii, czyli z tym samym numerem na początku i na końcu,
    jest poprawnym zapytaniem.

    Wyłapuje walidację, która wymaga co najmniej dwóch linii: przyczyną bywa jedna linia, na
    przykład warunek albo ustawienie."""
    query = QuoteCodeQuery(path=PATH, from_line=18, to_line=18, role="excluded")

    assert (query.from_line, query.to_line) == (18, 18)


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": PATH, "from_line": 0, "to_line": 3, "role": "cause"},      # linie liczy się od 1
        {"path": "",   "from_line": 1, "to_line": 3, "role": "cause"},      # pusta ścieżka
        {"path": PATH, "from_line": 1, "to_line": 3, "role": "cause", "text": "if (…)"},  # nieznany
    ],
    ids=["linia zero", "pusta ścieżka", "nieznany argument"],
)
def test_malformed_arguments_are_refused(arguments: dict) -> None:
    """Sprawdza, czy linia o numerze zero, pusta ścieżka i argument spoza schematu kończą się
    wyjątkiem `ValidationError`.

    Wyłapuje model zapytania, który przepuszcza takie argumenty: numer zero wskazywałby linię
    przed początkiem pliku, pusta ścieżka sam katalog z kodem, a nieznany argument zostałby po
    cichu pominięty, choć model myślałby, że coś nim przekazał."""
    with pytest.raises(ValidationError):
        QuoteCodeQuery(**arguments)
