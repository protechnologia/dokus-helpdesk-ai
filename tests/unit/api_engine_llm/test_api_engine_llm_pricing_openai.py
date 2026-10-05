import pytest

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.openai import PRICES, calculate_cost_usd, price_of


def test_prices_a_known_model():
    """Sprawdza, czy model z cennika (`gpt-5.4-mini`) dostaje swoje stawki: 0,75 USD za milion
    tokenów wejścia i 4,50 USD za milion tokenów wyjścia.

    Wyłapuje pomyłkę w stawkach tego modelu albo wyszukiwanie, które dla znanego modelu zgłasza
    błąd: koszt wywołań byłby wtedy policzony źle albo klient nie dałby się zbudować."""
    price = price_of("gpt-5.4-mini")

    assert price.input_per_million  == 0.75
    assert price.output_per_million == 4.50


def test_dated_snapshot_uses_its_alias_price():
    """Sprawdza, czy nazwa modelu z datą wydania na końcu (`gpt-5.4-mini-2026-03-17`) dostaje tę
    samą cenę co nazwa bez daty.

    Wyłapuje cennik, który szuka nazwy znak w znak: API odsyła właśnie nazwę z datą, więc model
    traciłby cenę po każdym nowym wydaniu."""
    # Zweryfikowane na żywym API 2026-08-02: prośba o "gpt-5.4-mini" wraca jako
    # "gpt-5.4-mini-2026-03-17". Wiersz na snapshot oznaczałby brak cennika po każdym wydaniu.
    assert price_of("gpt-5.4-mini-2026-03-17") == price_of("gpt-5.4-mini")


def test_unknown_model_fails_loudly():
    """Sprawdza, czy model spoza cennika kończy się wyjątkiem `LLMConfigError`, a komunikat podaje
    jego nazwę i listę znanych modeli (jest w niej `gpt-5.4-mini`).

    Wyłapuje cennik, który dla nieznanego modelu po cichu oddaje cenę zero: raport pokazywałby wtedy
    koszt 0,00 USD przy prawdziwym rachunku."""
    with pytest.raises(LLMConfigError) as exc:
        price_of("gpt-nieistniejacy")

    assert "gpt-nieistniejacy" in str(exc.value)
    assert "gpt-5.4-mini"      in str(exc.value)


def test_costs_input_and_output_at_their_own_rates():
    """Sprawdza, czy milion tokenów wejścia i milion tokenów wyjścia kosztują razem sumę obu stawek
    modelu `gpt-5.4-mini`: 0,75 + 4,50 USD.

    Wyłapuje rachunek, który stosuje jedną stawkę do obu stron: koszt byłby wtedy wyraźnie zły, bo
    wyjście jest kilka razy droższe od wejścia."""
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 1_000_000,
        completion_tokens = 1_000_000,
    )

    assert cost == pytest.approx(0.75 + 4.50)


def test_cached_tokens_are_billed_at_the_read_rate():
    """Sprawdza, czy milion tokenów odczytanych z cache, bez żadnego świeżego wejścia, kosztuje 10%
    stawki wejścia modelu `gpt-5.4-mini`.

    Wyłapuje rachunek, który odczyt z cache liczy pełną stawką wejścia albo wcale: koszt rozmowy
    korzystającej z cache byłby wtedy zawyżony dziesięć razy albo pominięty."""
    cost = calculate_cost_usd(
        model             = "gpt-5.4-mini",
        prompt_tokens     = 0,
        completion_tokens = 0,
        cache_read_tokens = 1_000_000,
    )

    assert cost == pytest.approx(0.75 * 0.10)


def test_cache_read_rate_follows_the_model():
    """Sprawdza, czy stawka za odczyt z cache zależy od modelu: 0,25 stawki wejścia dla `o4-mini`
    i `gpt-4.1`, 0,05 dla `gpt-6.1-sol` i 0,10 dla `gpt-5.4`.

    Wyłapuje jedną stałą stawkę odczytu dla wszystkich modeli: koszt rozmowy z cache byłby wtedy zły
    dla każdego modelu, który ma inny mnożnik."""
    def cached_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_read_tokens=1_000_000)

    assert cached_million("o4-mini")     == pytest.approx(1.10 * 0.25)
    assert cached_million("gpt-4.1")     == pytest.approx(2.00 * 0.25)
    assert cached_million("gpt-6.1-sol") == pytest.approx(2.00 * 0.05)
    assert cached_million("gpt-5.4")     == pytest.approx(2.50 * 0.10)


def test_cache_write_costs_more_in_the_new_families():
    """Sprawdza, czy w rodzinach `gpt-6` i `gpt-5.6` zapis do cache kosztuje 1,25 stawki wejścia:
    milion zapisanych tokenów to 2,50 USD dla `gpt-6.1-sol`, 12,50 dla `gpt-6-astra` i 5,00 dla
    `gpt-5.6-sol`.

    Wyłapuje rachunek, który zapis do cache liczy zwykłą stawką wejścia: zapis w nowych modelach
    byłby wtedy wyceniony o jedną piątą za nisko."""
    def written_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_write_tokens=1_000_000)

    assert written_million("gpt-6.1-sol") == pytest.approx(2.50)
    assert written_million("gpt-6-astra") == pytest.approx(12.50)
    assert written_million("gpt-5.6-sol") == pytest.approx(5.00)


def test_cache_write_is_plain_input_in_older_models():
    """Sprawdza, czy w starszych modelach, które nie mają osobnej stawki zapisu, milion tokenów
    zapisanych do cache kosztuje tyle, co zwykłe wejście: 0,75 USD dla `gpt-5.4-mini` i 1,10 dla
    `o4-mini`.

    Wyłapuje rachunek, który w tych modelach pomija zapisane tokeny albo dolicza do nich dopłatę:
    część wejścia byłaby wtedy darmowa albo za droga."""
    def written_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_write_tokens=1_000_000)

    assert written_million("gpt-5.4-mini") == pytest.approx(0.75)
    assert written_million("o4-mini")      == pytest.approx(1.10)


def test_cache_write_rate_follows_the_family():
    """Sprawdza, czy każdy wiersz cennika ma właściwy mnożnik zapisu do cache: 1,25 w rodzinach
    `gpt-6` i `gpt-5.6`, 1,00 w starszych.

    Wyłapuje pomyłkę w jednym wierszu tabeli, zanim trafi do rachunku: zły mnożnik zmienia koszt
    każdej rozmowy z tym modelem."""
    for model, price in PRICES.items():
        expected = 1.25 if model.startswith(("gpt-6", "gpt-5.6")) else 1.00

        assert price.cache_write_multiplier == expected, model


def test_token_classes_are_billed_side_by_side():
    """Sprawdza, czy milion tokenów w każdej z czterech klas naraz (świeże wejście, zapis do cache,
    odczyt z cache, wyjście) kosztuje sumę czterech stawek modelu `gpt-6.1-sol`: 14,60 USD.

    Wyłapuje rachunek, który jedną klasę liczy dwa razy albo odejmuje ją od innej: koszt tury
    z cache byłby wtedy zawyżony albo zaniżony."""
    cost = calculate_cost_usd(
        model              = "gpt-6.1-sol",
        prompt_tokens      = 1_000_000,   # 2,00 USD
        completion_tokens  = 1_000_000,   # 10,00 USD
        cache_write_tokens = 1_000_000,   # 2,50 USD
        cache_read_tokens  = 1_000_000,   # 0,10 USD
    )

    assert cost == pytest.approx(2.00 + 10.00 + 2.50 + 0.10)


def test_the_strongest_model_is_priced():
    """Sprawdza, czy najmocniejszy model z cennika (`gpt-6-astra`) ma swój wiersz: 10 USD za milion
    tokenów wejścia i 50 USD za milion tokenów wyjścia.

    Wyłapuje usunięcie tego wiersza albo pomyłkę w jego stawkach: klient nie dałby się zbudować
    z tym modelem albo najdroższe wywołania byłyby źle policzone."""
    price = price_of("gpt-6-astra")

    assert price.input_per_million  == 10.00
    assert price.output_per_million == 50.00


def test_reasoning_tokens_are_billed_as_output():
    """Sprawdza, czy milion tokenów wyjścia modelu `o4-mini` kosztuje 4,40 USD, czyli pełną stawkę
    wyjścia; w modelach rozumujących ten licznik obejmuje też tokeny rozumowania.

    Wyłapuje pomyłkę w stawce wyjścia modelu rozumującego: to rozumowanie, którego wołający nie
    widzi, tworzy tam większość rachunku."""
    # Sonda 2026-08-02: odpowiedź "OK" z o4-mini kosztowała 83 tokeny wyjścia — model płaci
    # za myślenie, którego wołający nie widzi.
    cost = calculate_cost_usd(model="o4-mini", prompt_tokens=0, completion_tokens=1_000_000)

    assert cost == pytest.approx(4.40)


def test_every_priced_model_has_positive_rates():
    """Sprawdza, czy każdy model z cennika ma stawki wejścia i wyjścia większe od zera.

    Wyłapuje wiersz z zerową stawką, wpisaną przez pomyłkę: przebieg na takim modelu wyglądałby na
    darmowy, choć dostawca wystawi za niego rachunek."""
    for model, price in PRICES.items():
        assert price.input_per_million  > 0, model
        assert price.output_per_million > 0, model
