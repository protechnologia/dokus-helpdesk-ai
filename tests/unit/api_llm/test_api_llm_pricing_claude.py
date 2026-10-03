import pytest

from app.llm import LLMConfigError
from app.llm.pricing_claude import PRICES, calculate_cost_usd, price_of


def test_known_model_has_price():
    """Model z tabeli → zwrócony wiersz cennika ze stawkami wejścia i wyjścia."""
    price = price_of("claude-haiku-4-5")

    assert price.input_per_million  == 1.00
    assert price.output_per_million == 5.00


def test_dated_snapshot_is_priced_as_its_alias():
    """Model z sufiksem daty → wyceniony jak alias; API odsyła snapshot, o który nie prosiliśmy."""
    # Zaobserwowane na żywym API 2026-08-01: żądanie "claude-haiku-4-5" wraca jako
    # "claude-haiku-4-5-20251001". Wiersz per snapshot oznaczałby brak ceny przy każdym wydaniu.
    assert price_of("claude-haiku-4-5-20251001") == price_of("claude-haiku-4-5")


def test_cost_of_dated_snapshot_matches_the_alias():
    """Koszt liczony po snapshotcie = koszt po aliasie; sufiks nie zmienia stawek."""
    dated = calculate_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    alias = calculate_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000)

    assert dated == alias


def test_unknown_model_with_date_suffix_still_raises():
    """Nieznany model z datą → nadal błąd; obcięcie sufiksu nie może przemycić obcego modelu."""
    with pytest.raises(LLMConfigError):
        price_of("claude-nieistniejacy-9-20260101")


def test_unknown_model_raises_config_error():
    """Model spoza tabeli → LLMConfigError, nie cichy koszt 0.00."""
    with pytest.raises(LLMConfigError) as exc:
        price_of("claude-nieistniejacy-9")

    # Komunikat ma prowadzić do naprawy: nazwa modelu i miejsce, gdzie dopisać stawki.
    assert "claude-nieistniejacy-9" in str(exc.value)
    assert "pricing_claude.py" in str(exc.value)


def test_cost_of_plain_call():
    """Wywołanie bez cache → koszt = tokeny wejścia * stawka in + tokeny wyjścia * stawka out."""
    # 1 000 000 wejścia po 1 USD + 1 000 000 wyjścia po 5 USD = 6 USD.
    cost = calculate_cost_usd(
        model             = "claude-haiku-4-5",
        prompt_tokens     = 1_000_000,
        completion_tokens = 1_000_000,
    )

    assert cost == pytest.approx(6.00)


def test_cached_tokens_are_billed_at_their_own_rates():
    """Tokeny cache liczone mnożnikami (zapis 1,25x, odczyt 0,1x), nie stawką wejścia."""
    cost = calculate_cost_usd(
        model              = "claude-haiku-4-5",
        prompt_tokens      = 0,
        completion_tokens  = 0,
        cache_write_tokens = 1_000_000,   # 1.25 USD
        cache_read_tokens  = 1_000_000,   # 0.10 USD
    )

    assert cost == pytest.approx(1.35)


def test_cache_read_is_cheaper_than_fresh_input():
    """Ta sama liczba tokenów odczytana z cache kosztuje mniej niż policzona od nowa."""
    fresh  = calculate_cost_usd("claude-haiku-4-5", prompt_tokens=100_000, completion_tokens=0)
    cached = calculate_cost_usd(
        "claude-haiku-4-5", prompt_tokens=0, completion_tokens=0, cache_read_tokens=100_000
    )

    # Gdyby klient zliczał cache do prompt_tokens, obie wartości byłyby równe — a raport kosztu
    # zawyżałby przebieg korzystający z cache o rząd wielkości.
    assert cached < fresh


def test_zero_usage_costs_nothing():
    """Zero tokenów → koszt 0.0, bez dzielenia przez zero i bez stałej minimalnej."""
    assert calculate_cost_usd("claude-haiku-4-5", prompt_tokens=0, completion_tokens=0) == 0.0


@pytest.mark.parametrize("model", sorted(PRICES))
def test_every_priced_model_has_positive_rates(model: str):
    """Każdy wiersz cennika ma dodatnie stawki — zero oznaczałoby darmowy model."""
    price = PRICES[model]

    assert price.input_per_million  > 0
    assert price.output_per_million > 0


def test_output_costs_more_than_input():
    """Dla każdego modelu wyjście jest droższe niż wejście — odwrotnie byłoby literówką w tabeli."""
    for model, price in PRICES.items():
        assert price.output_per_million > price.input_per_million, model
