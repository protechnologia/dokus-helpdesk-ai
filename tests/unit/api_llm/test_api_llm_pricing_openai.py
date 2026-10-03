import pytest

from app.llm.errors import LLMConfigError
from app.llm.pricing_openai import PRICES, calculate_cost_usd, price_of


def test_prices_a_known_model():
    """Model z cennika → stawki wejścia i wyjścia, nie wyjątek."""
    price = price_of("gpt-5.4-mini")

    assert price.input_per_million  == 0.75
    assert price.output_per_million == 4.50


def test_dated_snapshot_uses_its_alias_price():
    """Snapshot z datą → cena aliasu; API odsyła właśnie taki identyfikator."""
    # Zweryfikowane na żywym API 2026-08-02: prośba o "gpt-5.4-mini" wraca jako
    # "gpt-5.4-mini-2026-03-17". Wiersz na snapshot oznaczałby brak cennika po każdym wydaniu.
    assert price_of("gpt-5.4-mini-2026-03-17") == price_of("gpt-5.4-mini")


def test_unknown_model_fails_loudly():
    """Model spoza cennika → LLMConfigError z listą znanych, nie cena zero."""
    with pytest.raises(LLMConfigError) as exc:
        price_of("gpt-nieistniejacy")

    assert "gpt-nieistniejacy" in str(exc.value)
    assert "gpt-5.4-mini"      in str(exc.value)


def test_costs_input_and_output_at_their_own_rates():
    """Milion wejścia + milion wyjścia → suma obu stawek, nie jedna zastosowana dwa razy."""
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 1_000_000,
        completion_tokens = 1_000_000,
    )

    assert cost == pytest.approx(0.75 + 4.50)


def test_cached_tokens_are_discounted_not_added():
    """Tokeny z cache siedzą już w prompt_tokens → liczone taniej, nie doliczane drugi raz."""
    # 1 000 000 wejścia, z czego 1 000 000 z cache: 10% stawki zamiast pełnej.
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 1_000_000,
        completion_tokens = 0,
        cache_read_tokens = 1_000_000,
    )

    assert cost == pytest.approx(0.75 * 0.10)


def test_cache_larger_than_prompt_does_not_go_negative():
    """Cache większy niż prompt → koszt nieujemny; arytmetyka nie może zwrócić ujemnego rachunku."""
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 100,
        completion_tokens = 0,
        cache_read_tokens = 5_000,
    )

    assert cost >= 0


def test_reasoning_tokens_are_billed_as_output():
    """Tokeny rozumowania → stawka wyjścia; przy o4-mini to one tworzą rachunek."""
    # Sonda 2026-08-02: odpowiedź "OK" z o4-mini kosztowała 83 tokeny wyjścia — model płaci
    # za myślenie, którego wołający nie widzi.
    cost = calculate_cost_usd(model="o4-mini", prompt_tokens=0, completion_tokens=1_000_000)

    assert cost == pytest.approx(4.40)


def test_every_priced_model_has_positive_rates():
    """Każdy wiersz cennika → stawki dodatnie; zero przemyciłoby darmowy przebieg."""
    for model, price in PRICES.items():
        assert price.input_per_million  > 0, model
        assert price.output_per_million > 0, model
