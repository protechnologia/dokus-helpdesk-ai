import pytest

from app.engine_llm import LLMConfigError
from app.engine_llm.pricing.claude import PRICES, calculate_cost_usd, price_of


def test_known_model_has_price():
    """Sprawdza, czy model z cennika (`claude-haiku-4-5`) dostaje swój wiersz: 1 USD za milion
    tokenów wejścia i 5 USD za milion tokenów wyjścia.

    Wyłapuje pomyłkę w stawkach tego modelu albo wyszukiwanie, które oddaje cudzy wiersz: koszt
    każdego wywołania byłby wtedy policzony źle."""
    price = price_of("claude-haiku-4-5")

    assert price.input_per_million  == 1.00
    assert price.output_per_million == 5.00


def test_dated_snapshot_is_priced_as_its_alias():
    """Sprawdza, czy nazwa modelu z datą na końcu (`claude-haiku-4-5-20251001`) dostaje tę samą cenę
    co nazwa bez daty.

    Wyłapuje cennik, który szuka nazwy znak w znak: API odsyła właśnie nazwę z datą, o którą nie
    prosiliśmy, więc model traciłby cenę przy każdym nowym wydaniu."""
    # Zaobserwowane na żywym API 2026-08-01: żądanie "claude-haiku-4-5" wraca jako
    # "claude-haiku-4-5-20251001". Wiersz per snapshot oznaczałby brak ceny przy każdym wydaniu.
    assert price_of("claude-haiku-4-5-20251001") == price_of("claude-haiku-4-5")


def test_cost_of_dated_snapshot_matches_the_alias():
    """Sprawdza, czy koszt miliona tokenów wejścia i miliona tokenów wyjścia jest taki sam dla nazwy
    modelu z datą i bez daty.

    Wyłapuje liczenie kosztu, które dla nazwy z datą bierze inne stawki albo zgłasza błąd, choć data
    w nazwie niczego w cenie nie zmienia."""
    dated = calculate_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    alias = calculate_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000)

    assert dated == alias


def test_unknown_model_with_date_suffix_still_raises():
    """Sprawdza, czy nieznany model z datą na końcu (`claude-nieistniejacy-9-20260101`) nadal kończy
    się błędem konfiguracji.

    Wyłapuje obcinanie daty, które przy okazji dopasowuje obcy model do któregoś wiersza: model
    spoza cennika dostałby wtedy cudzą cenę zamiast błędu."""
    with pytest.raises(LLMConfigError):
        price_of("claude-nieistniejacy-9-20260101")


def test_unknown_model_raises_config_error():
    """Sprawdza, czy model spoza cennika kończy się wyjątkiem `LLMConfigError`, a komunikat podaje
    nazwę modelu i plik, w którym dopisuje się stawki.

    Wyłapuje cennik, który dla nieznanego modelu po cichu oddaje cenę zero: raport pokazywałby wtedy
    koszt 0,00 USD przy prawdziwym rachunku."""
    with pytest.raises(LLMConfigError) as exc:
        price_of("claude-nieistniejacy-9")

    # Komunikat ma prowadzić do naprawy: nazwa modelu i miejsce, gdzie dopisać stawki.
    assert "claude-nieistniejacy-9" in str(exc.value)
    assert "pricing/claude.py" in str(exc.value)


def test_cost_of_plain_call():
    """Sprawdza, czy koszt wywołania bez cache to tokeny wejścia razy stawka wejścia plus tokeny
    wyjścia razy stawka wyjścia: milion wejścia po 1 USD i milion wyjścia po 5 USD daje 6 USD.

    Wyłapuje błąd w podstawowym rachunku, na przykład jedną stawkę zastosowaną do obu stron albo
    pomyłkę w przeliczeniu stawki podanej za milion tokenów."""
    # 1 000 000 wejścia po 1 USD + 1 000 000 wyjścia po 5 USD = 6 USD.
    cost = calculate_cost_usd(
        model             = "claude-haiku-4-5",
        prompt_tokens     = 1_000_000,
        completion_tokens = 1_000_000,
    )

    assert cost == pytest.approx(6.00)


def test_cached_tokens_are_billed_at_their_own_rates():
    """Sprawdza, czy tokeny cache mają własne stawki: milion zapisanych kosztuje 1,25 stawki
    wejścia, a milion odczytanych 0,1 tej stawki, razem 1,35 USD.

    Wyłapuje rachunek, który liczy tokeny cache zwykłą stawką wejścia albo wcale: koszt przebiegu
    korzystającego z cache byłby wtedy zawyżony albo zaniżony."""
    cost = calculate_cost_usd(
        model              = "claude-haiku-4-5",
        prompt_tokens      = 0,
        completion_tokens  = 0,
        cache_write_tokens = 1_000_000,   # 1.25 USD
        cache_read_tokens  = 1_000_000,   # 0.10 USD
    )

    assert cost == pytest.approx(1.35)


def test_cache_read_rate_follows_the_model():
    """Sprawdza, czy stawka za odczyt z cache zależy od modelu: `claude-fable-5-1` płaci 0,025
    stawki wejścia, `claude-opus-5-5` 0,05, a `claude-sonnet-5-5` 0,10.

    Wyłapuje jedną stałą stawkę odczytu dla wszystkich modeli: koszt rozmowy z cache byłby wtedy
    zawyżony dla modeli, które mają odczyt tańszy."""
    def cached_million(model: str) -> float:
        return calculate_cost_usd(model, 0, 0, cache_read_tokens=1_000_000)

    assert cached_million("claude-fable-5-1")  == pytest.approx(10.00 * 0.025)
    assert cached_million("claude-opus-5-5")   == pytest.approx( 4.00 * 0.05)
    assert cached_million("claude-sonnet-5-5") == pytest.approx( 2.00 * 0.10)


def test_cache_write_rate_comes_from_the_row():
    """Sprawdza, czy każdy model z cennika ma w swoim wierszu mnożnik zapisu do cache 1,25 i czy
    milion zapisanych tokenów kosztuje 1,25 stawki wejścia tego modelu.

    Wyłapuje wiersz z pomylonym mnożnikiem zapisu oraz rachunek, który liczy zapis zwykłą stawką
    wejścia: nowe wejście zapisywane do cache byłoby wtedy wycenione źle."""
    for model, price in PRICES.items():
        cost = calculate_cost_usd(model, 0, 0, cache_write_tokens=1_000_000)

        assert price.cache_write_multiplier == 1.25, model
        assert cost == pytest.approx(price.input_per_million * 1.25), model


def test_the_strongest_model_is_priced():
    """Sprawdza, czy najmocniejszy model z cennika (`claude-fable-5-1`) ma swój wiersz: 10 USD za
    milion tokenów wejścia i 50 USD za milion tokenów wyjścia.

    Wyłapuje usunięcie tego wiersza albo pomyłkę w jego stawkach: bez wiersza klient odmówiłby
    startu z tym modelem, a ze złą stawką najdroższe wywołania byłyby źle policzone."""
    price = price_of("claude-fable-5-1")

    assert price.input_per_million  == 10.00
    assert price.output_per_million == 50.00


def test_cache_read_is_cheaper_than_fresh_input():
    """Sprawdza, czy 100 tysięcy tokenów odczytanych z cache kosztuje mniej niż ta sama liczba
    tokenów policzona jako świeże wejście.

    Wyłapuje rachunek, który odczyt z cache liczy pełną stawką wejścia: raport zawyżałby wtedy koszt
    przebiegu korzystającego z cache o rząd wielkości."""
    fresh  = calculate_cost_usd("claude-haiku-4-5", prompt_tokens=100_000, completion_tokens=0)
    cached = calculate_cost_usd(
        "claude-haiku-4-5", prompt_tokens=0, completion_tokens=0, cache_read_tokens=100_000
    )

    # Gdyby klient zliczał cache do prompt_tokens, obie wartości byłyby równe — a raport kosztu
    # zawyżałby przebieg korzystający z cache o rząd wielkości.
    assert cached < fresh


def test_zero_usage_costs_nothing():
    """Sprawdza, czy wywołanie z zerową liczbą tokenów kosztuje dokładnie 0,0.

    Wyłapuje rachunek, który dolicza stałą opłatę minimalną albo wywraca się na zerach, na przykład
    przez dzielenie przez zero."""
    assert calculate_cost_usd("claude-haiku-4-5", prompt_tokens=0, completion_tokens=0) == 0.0


@pytest.mark.parametrize("model", sorted(PRICES))
def test_every_priced_model_has_positive_rates(model: str):
    """Sprawdza, czy każdy model z cennika ma stawki wejścia i wyjścia większe od zera.

    Wyłapuje wiersz z zerową stawką, wpisaną przez pomyłkę: model wyglądałby wtedy na darmowy,
    a raport pokazywałby zaniżony koszt."""
    price = PRICES[model]

    assert price.input_per_million  > 0
    assert price.output_per_million > 0


def test_output_costs_more_than_input():
    """Sprawdza, czy u każdego modelu z cennika token wyjścia jest droższy niż token wejścia.

    Wyłapuje stawki wejścia i wyjścia zamienione miejscami w wierszu: taka literówka w tabeli
    zaniżałaby koszt odpowiedzi modelu i zawyżała koszt promptu."""
    for model, price in PRICES.items():
        assert price.output_per_million > price.input_per_million, model
