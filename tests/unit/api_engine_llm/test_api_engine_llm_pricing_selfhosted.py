from app.engine_llm.pricing.selfhosted import calculate_cost_usd, price_of


def test_every_model_is_free():
    """Sprawdza, czy model uruchamiany na własnym sprzęcie (tu Bielik) ma zerowe stawki wejścia
    i wyjścia.

    Wyłapuje cennik, który przypisuje takiemu modelowi cenę: raport pokazywałby wtedy koszt, choć za
    tokeny na własnym sprzęcie nikt nie płaci."""
    price = price_of("SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0")

    assert price.input_per_million  == 0.0
    assert price.output_per_million == 0.0


def test_unknown_model_does_not_fail():
    """Sprawdza, czy dowolna, nieznana wcześniej nazwa modelu (`cokolwiek/nowy-model:latest`) też
    dostaje stawkę zero zamiast błędu.

    Wyłapuje przeniesienie tu reguły z cenników dostawców chmurowych, gdzie nieznany model to błąd:
    tam chroni to przed prawdziwym rachunkiem pokazanym jako zero, a na własnym sprzęcie rachunku
    nie ma, więc odmowa blokowałaby przebieg bez powodu."""
    # Tam nieznany model to LLMConfigError, bo cichy $0.00 ukryłby prawdziwy rachunek. Tu rachunku
    # nie ma, więc blokada odmawiałaby przebiegu bez powodu.
    assert price_of("cokolwiek/nowy-model:latest").input_per_million == 0.0


def test_cost_is_zero_regardless_of_volume():
    """Sprawdza, czy koszt wywołania modelu na własnym sprzęcie jest równy zero także przy milionie
    tokenów w każdej z czterech klas.

    Wyłapuje rachunek, który przy dużej liczbie tokenów zaczyna coś doliczać: zero jest tu prawdziwą
    ceną, a nie wynikiem zaokrąglenia małej kwoty."""
    cost = calculate_cost_usd(
        model              = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
        prompt_tokens      = 1_000_000,
        completion_tokens  = 1_000_000,
        cache_write_tokens = 1_000_000,
        cache_read_tokens  = 1_000_000,
    )

    assert cost == 0.0
