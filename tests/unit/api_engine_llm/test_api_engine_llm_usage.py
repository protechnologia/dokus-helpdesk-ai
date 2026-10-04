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
    """Zużycie bez wywołań → same zera: od tego zaczyna stan grafu, a przebieg bez modelu
    kosztuje zero, nie „brak danych"."""
    assert LLMUsage().model_dump() == {
        "calls":              0,
        "prompt_tokens":      0,
        "completion_tokens":  0,
        "cache_write_tokens": 0,
        "cache_read_tokens":  0,
        "cost_usd":           0.0,
    }


def test_usage_of_one_call_copies_the_completion() -> None:
    """Odpowiedź modelu → zużycie jednego wywołania z tokenami wszystkich czterech klas
    i kosztem policzonym przez klienta dostawcy."""
    usage = LLMUsage.from_completion(COMPLETION)

    assert usage.calls              == 1
    assert usage.prompt_tokens      == 4820
    assert usage.completion_tokens  == 640
    assert usage.cache_write_tokens == 1200
    assert usage.cache_read_tokens  == 1830
    assert usage.cost_usd           == 0.0321


def test_two_usages_add_up_field_by_field() -> None:
    """Dwa zużycia → suma każdego pola: tak stan grafu zbiera koszt kolejnych tur modelu."""
    first  = LLMUsage.from_completion(COMPLETION)
    second = LLMUsage(calls=1, prompt_tokens=180, completion_tokens=60, cost_usd=0.002)

    total = first.plus(second)

    assert total.calls             == 2
    assert total.prompt_tokens     == 5000
    assert total.completion_tokens == 700
    assert total.cache_read_tokens == 1830
    assert total.cost_usd          == pytest.approx(0.0341)


def test_adding_leaves_both_sides_unchanged() -> None:
    """Sumowanie → nowy obiekt, oba składniki bez zmian: reduktor stanu nie może psuć zużycia,
    które zwrócił węzeł."""
    first  = LLMUsage(calls=1, cost_usd=0.01)
    second = LLMUsage(calls=1, cost_usd=0.02)

    first.plus(second)

    assert (first.calls, first.cost_usd)   == (1, 0.01)
    assert (second.calls, second.cost_usd) == (1, 0.02)


def test_a_negative_cost_is_refused() -> None:
    """Koszt ujemny → `ValidationError`: zużycie tylko rośnie, a ujemna liczba ukryłaby koszt
    pozostałych tur."""
    with pytest.raises(ValidationError):
        LLMUsage(calls=1, cost_usd=-0.01)
