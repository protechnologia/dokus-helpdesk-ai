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
    """Sprawdza, czy rozwiązanie, które tylko przyznaje, że rozwiązania nie ma, liczy się jako brak
    rozwiązania. Sześć przypadków: „brak", „Brak.", „nie dotyczy" i trzy krótkie zdania w rodzaju
    „Nie ustalono rozwiązania.".

    Wyłapuje pusty zapis wzięty za treść: parser często pisze całe zdanie zamiast samego „brak",
    a takiego zgłoszenia nie ma po co proponować komuś innemu."""
    assert no_solution(solution)


@pytest.mark.parametrize("solution", [
    "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "Dodano brakujące ustawienie systemowe.",
    "Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować dokument ponownie, "
    "a dopiero potem wysłać go przez ePUAP z poziomu rejestru wysyłek.",
])
def test_a_solution_with_content_is_kept(solution: str) -> None:
    """Sprawdza, czy rozwiązanie z treścią nie jest brane za puste. Trzy przypadki: zwykły opis
    wykonanej pracy, słowo „brakujące", w którym „brak" jest tylko początkiem, oraz odmowa, która
    zaczyna się od „Brak możliwości", ale podaje uzasadnienie.

    Wyłapuje rozpoznawanie pustki po samym słowie „brak": odmowa mówi, czego nie próbować, więc jest
    wiedzą, a taka reguła wycięłaby ją razem z opisami wykonanej pracy."""
    assert not no_solution(solution)


def test_the_word_limit_is_the_boundary_between_hollow_and_content() -> None:
    """Sprawdza, czy granica między pustym zapisem a treścią leży dokładnie na progu
    `MAX_HOLLOW_EXTRA_WORDS`: „brak" i tyle dodatkowych słów, ile wynosi próg, to nadal brak
    rozwiązania, a jedno słowo więcej to już treść.

    Wyłapuje przesunięcie tej granicy o jedno słowo, na przykład przez zamianę „najwyżej tyle" na
    „mniej niż tyle": zmieniłoby to bez żadnego błędu, które zgłoszenia filtr odrzuca."""
    at_limit   = "brak " + " ".join(["słowo"] * MAX_HOLLOW_EXTRA_WORDS)
    over_limit = at_limit + " słowo"

    assert no_solution(at_limit)
    assert not no_solution(over_limit)
