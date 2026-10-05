import pytest

from app.core_service.normalizer_ticket_sentinel import MAX_HOLLOW_EXTRA_WORDS, no_solution


@pytest.mark.parametrize("solution", [
    "brak",
    "Brak.",
    "nie dotyczy",
    "Brak rozstrzygnięcia w wątku.",
    "Nie ustalono rozwiązania.",
    "W wątku nie podano rozwiązania.",
])
def test_a_solution_that_only_admits_there_is_none_counts_as_missing(solution: str) -> None:
    """Fraza ucieczkowa i niewiele poza nią → brak rozwiązania: takiego rekordu nie ma po co
    proponować komuś innemu."""
    assert no_solution(solution)


@pytest.mark.parametrize("solution", [
    "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "Dodano brakujące ustawienie systemowe.",
    "Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować dokument ponownie, "
    "a dopiero potem wysłać go przez ePUAP z poziomu rejestru wysyłek.",
])
def test_a_solution_with_content_is_kept(solution: str) -> None:
    """Treść bez frazy ucieczkowej, „brakujące" w środku słowa albo odmowa z uzasadnieniem →
    rozwiązanie jest: odmowa mówi, czego nie próbować, więc to wiedza, nie pustka."""
    assert not no_solution(solution)


def test_the_word_limit_is_the_boundary_between_hollow_and_content() -> None:
    """Fraza ucieczkowa i tyle słów, ile wynosi próg → brak; jedno słowo więcej → treść."""
    at_limit   = "brak " + " ".join(["słowo"] * MAX_HOLLOW_EXTRA_WORDS)
    over_limit = at_limit + " słowo"

    assert no_solution(at_limit)
    assert not no_solution(over_limit)
