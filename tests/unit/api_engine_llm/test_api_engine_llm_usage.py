import pytest
from pydantic import ValidationError

from app.engine_llm import LLMCompletion, LLMUsage

# Zużycie modelu w przebiegu grafu: suma rozliczeń kolejnych wywołań.

COMPLETION = LLMCompletion(
    text               = "{}",
    model              = "claude-opus-5-5",
    prompt_tokens      = 4820,
    completion_tokens  = 640,
    latency_ms         = 3120.4,
    cache_write_tokens = 1200,
    cache_read_tokens  = 1830,
    cost_usd           = 0.0321,
)


def test_an_empty_usage_is_all_zeros() -> None:
    """Sprawdza, czy zużycie modelu utworzone bez żadnych danych ma same zera: zero wywołań, zero
    tokenów w każdej z czterech klas i koszt 0,0.

    Wyłapuje wartości początkowe inne niż zero albo puste: od takiego zużycia zaczyna stan grafu,
    więc przebieg bez wywołań modelu ma pokazywać zerowy koszt, a nie brak danych."""
    assert LLMUsage().model_dump() == {
        "calls":              0,
        "prompt_tokens":      0,
        "completion_tokens":  0,
        "cache_write_tokens": 0,
        "cache_read_tokens":  0,
        "cost_usd":           0.0,
    }


def test_usage_of_one_call_copies_the_completion() -> None:
    """Sprawdza, czy zużycie zrobione z jednej odpowiedzi modelu to jedno wywołanie z tymi samymi
    liczbami tokenów we wszystkich czterech klasach i z kosztem, który policzył klient dostawcy.

    Wyłapuje przepisanie, które gubi albo zamienia miejscami którąś klasę tokenów, na przykład
    pomija tokeny cache: suma zużycia przebiegu byłaby wtedy niezgodna z rachunkiem."""
    usage = LLMUsage.from_completion(COMPLETION)

    assert usage.calls              == 1
    assert usage.prompt_tokens      == 4820
    assert usage.completion_tokens  == 640
    assert usage.cache_write_tokens == 1200
    assert usage.cache_read_tokens  == 1830
    assert usage.cost_usd           == 0.0321


def test_two_usages_add_up_field_by_field() -> None:
    """Sprawdza, czy suma dwóch zużyć to suma każdego pola osobno: dwa wywołania, 4820 + 180 tokenów
    wejścia, 640 + 60 tokenów wyjścia i koszt 0,0321 + 0,002 USD.

    Wyłapuje sumowanie, które pomija któreś pole albo bierze je tylko z jednej strony: stan grafu
    zbiera tak koszt kolejnych tur modelu, więc odpowiedź pokazywałaby za mały koszt sprawy."""
    first  = LLMUsage.from_completion(COMPLETION)
    second = LLMUsage(calls=1, prompt_tokens=180, completion_tokens=60, cost_usd=0.002)

    total = first.plus(second)

    assert total.calls             == 2
    assert total.prompt_tokens     == 5000
    assert total.completion_tokens == 700
    assert total.cache_read_tokens == 1830
    assert total.cost_usd          == pytest.approx(0.0341)


def test_adding_leaves_both_sides_unchanged() -> None:
    """Sprawdza, czy po zsumowaniu dwóch zużyć oba składniki mają te same liczby co przedtem.

    Wyłapuje sumowanie, które dopisuje wynik do jednego ze składników: stan grafu sumuje zużycie po
    każdej turze i psułby wtedy liczby, które zwrócił węzeł."""
    first  = LLMUsage(calls=1, cost_usd=0.01)
    second = LLMUsage(calls=1, cost_usd=0.02)

    first.plus(second)

    assert (first.calls, first.cost_usd)   == (1, 0.01)
    assert (second.calls, second.cost_usd) == (1, 0.02)


def test_a_negative_cost_is_refused() -> None:
    """Sprawdza, czy zużycie z ujemnym kosztem jest odrzucane wyjątkiem `ValidationError`.

    Wyłapuje model, który przyjmuje ujemną liczbę: zużycie może tylko rosnąć, a ujemny koszt jednej
    tury ukryłby w sumie koszt pozostałych."""
    with pytest.raises(ValidationError):
        LLMUsage(calls=1, cost_usd=-0.01)
