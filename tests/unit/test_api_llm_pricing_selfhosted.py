from app.llm.pricing_selfhosted import calculate_cost_usd, price_of


def test_every_model_is_free():
    """Dowolny model self-hosted → stawki zerowe; nie płacimy za tokeny na własnym sprzęcie."""
    price = price_of("SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0")

    assert price.input_per_million  == 0.0
    assert price.output_per_million == 0.0


def test_unknown_model_does_not_fail():
    """Nieznany tag → zero, nie wyjątek; inaczej niż w cennikach chmurowych."""
    # Tam nieznany model to LLMConfigError, bo cichy $0.00 ukryłby prawdziwy rachunek. Tu rachunku
    # nie ma, więc blokada odmawiałaby przebiegu bez powodu.
    assert price_of("cokolwiek/nowy-model:latest").input_per_million == 0.0


def test_cost_is_zero_regardless_of_volume():
    """Milion tokenów w każdej klasie → nadal zero; to nie zaokrąglenie, tylko brak rachunku."""
    cost = calculate_cost_usd(
        model             = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
        prompt_tokens     = 1_000_000,
        completion_tokens = 1_000_000,
        cache_read_tokens = 1_000_000,
    )

    assert cost == 0.0
