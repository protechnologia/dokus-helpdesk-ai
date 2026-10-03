import pytest

from app.service.normalizer_sentinel import MAX_HOLLOW_EXTRA_WORDS, no_cause, no_solution


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


@pytest.mark.parametrize("cause", [
    "brak",
    "Brak",
    "Brak.",
    "nie dotyczy",
    "Brak ustalonej przyczyny w wątku.",
    "Brak informacji o przyczynie w wątku",
    "Brak szczegółów dotyczących przyczyny awarii w treści wątku",
    "Brak ustalonej przyczyny, ale problem został rozwiązany przez dodanie wizualizacji.",
])
def test_a_cause_that_was_not_established_counts_as_missing(cause: str) -> None:
    """Jawne wyjście schematu albo zdanie „brak … przyczyny" → brak przyczyny: brak wiedzy nie
    może wyglądać jak przyczyna."""
    assert no_cause(cause)


@pytest.mark.parametrize("cause", [
    "Brak uprawnienia do kancelarii",
    "Brak miejsca na dysku",
    "Brak konfiguracji skrzynki ePUAP jako typu asynchronicznego.",
    "Certyfikat bez uprawnienia AddDocumentToSign",
])
def test_a_real_cause_starting_with_brak_is_a_cause(cause: str) -> None:
    """Przyczyna zaczynająca się od „brak" → przyczyna jest: prefiks nie rozstrzyga, „Brak
    uprawnienia do kancelarii" to pełnoprawna przyczyna."""
    assert not no_cause(cause)


def test_the_same_sentence_means_different_things_in_the_two_fields() -> None:
    """„Brak uprawnienia do kancelarii" → jest przyczyną, ale nie jest rozwiązaniem: dlatego
    każde pole ma własną regułę."""
    sentence = "Brak uprawnienia do kancelarii"

    assert not no_cause(sentence)
    assert no_solution(sentence)
