import pytest

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.openai import PRICES, calculate_cost_usd, price_of


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


def test_cached_tokens_are_billed_at_the_read_rate():
    """Milion tokenów odczytanych z cache → 10% stawki wejścia, bez świeżego wejścia obok."""
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 0,
        completion_tokens = 0,
        cache_read_tokens = 1_000_000,
    )

    assert cost == pytest.approx(0.75 * 0.10)


def test_cache_read_rate_follows_the_model():
    """Odczyt z cache → mnożnik z wiersza modelu: 0,25 stawki wejścia dla o4-mini i gpt-4.1,
    0,05 dla gpt-6.1-sol, 0,10 dla pozostałych."""
    def cached_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_read_tokens=1_000_000)

    assert cached_million("o4-mini")     == pytest.approx(1.10 * 0.25)
    assert cached_million("gpt-4.1")     == pytest.approx(2.00 * 0.25)
    assert cached_million("gpt-6.1-sol") == pytest.approx(2.00 * 0.05)
    assert cached_million("gpt-5.4")     == pytest.approx(2.50 * 0.10)


def test_cache_write_costs_more_in_the_new_families():
    """Zapis do cache → 1,25 stawki wejścia w rodzinach gpt-6 i gpt-5.6, zgodnie z cennikiem
    (gpt-6.1-sol: 2,50 USD za milion przy wejściu 2,00)."""
    def written_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_write_tokens=1_000_000)

    assert written_million("gpt-6.1-sol") == pytest.approx(2.50)
    assert written_million("gpt-6-astra") == pytest.approx(12.50)
    assert written_million("gpt-5.6-sol") == pytest.approx(5.00)


def test_cache_write_is_plain_input_in_older_models():
    """Model bez osobnej stawki zapisu → zapis po zwykłej stawce wejścia, nie za darmo."""
    def written_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_write_tokens=1_000_000)

    assert written_million("gpt-5.4-mini") == pytest.approx(0.75)
    assert written_million("o4-mini")      == pytest.approx(1.10)


def test_cache_write_rate_follows_the_family():
    """Każdy wiersz cennika → mnożnik zapisu 1,25 w rodzinach gpt-6 i gpt-5.6, 1,00 w starszych;
    pomyłka w jednym wierszu ma paść tutaj, nie w rachunku."""
    for model, price in PRICES.items():
        expected = 1.25 if model.startswith(("gpt-6", "gpt-5.6")) else 1.00

        assert price.cache_write_multiplier == expected, model


def test_token_classes_are_billed_side_by_side():
    """Świeże wejście, zapis, odczyt i wyjście naraz → suma czterech stawek; żadna klasa nie jest
    liczona dwa razy ani odejmowana od innej."""
    cost = calculate_cost_usd(
        model              = "gpt-6.1-sol",
        prompt_tokens      = 1_000_000,   # 2,00 USD
        completion_tokens  = 1_000_000,   # 10,00 USD
        cache_write_tokens = 1_000_000,   # 2,50 USD
        cache_read_tokens  = 1_000_000,   # 0,10 USD
    )

    assert cost == pytest.approx(2.00 + 10.00 + 2.50 + 0.10)


def test_the_strongest_model_is_priced():
    """Najmocniejszy model z cennika → 10 USD za milion wejścia i 50 za milion wyjścia."""
    price = price_of("gpt-6-astra")

    assert price.input_per_million  == 10.00
    assert price.output_per_million == 50.00


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
