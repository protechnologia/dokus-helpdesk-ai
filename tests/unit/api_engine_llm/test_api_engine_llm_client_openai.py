import pytest

from app.engine_llm import LLMError
from app.engine_llm.client.openai import MODELS_ACCEPTING_TEMPERATURE, OpenAILLMClient
from app.engine_llm.pricing.openai import PRICES

# Klient OpenAI na API Responses: kształt żądania, mapowanie odpowiedzi na `LLMCompletion`
# i reguła `temperature`. Bez sieci — testy wołają `_build_request()` i `_to_completion()` wprost.

API_KEY = "sk-proj-test-key"
MODEL   = "gpt-5.4-mini"

# Modele, które odrzucają `temperature` błędem 400 (sprawdzone na żywym API 2026-10-04).
MODELS_WITHOUT_TEMPERATURE = [
    "gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna",
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "o4-mini",
]

# Modele, które ją przyjmują.
MODELS_WITH_TEMPERATURE = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1", "gpt-4.1-mini"]


class StubUsage:
    """
    Description:
    Liczniki zużycia w atrapie odpowiedzi. Liczniki cache przychodzą zagnieżdżone pod
    `input_tokens_details` i siedzą WEWNĄTRZ `input_tokens`, więc atrapa odwzorowuje ten kształt.
    """

    def __init__(
        self,
        input_tokens:       int,      # np. 4820 — całe wejście, razem z licznikami cache
        output_tokens:      int,      # np. 640
        cached_tokens:      int = 0,  # np. 1830
        cache_write_tokens: int = 0,  # np. 1024
    ):
        details = {"cached_tokens": cached_tokens, "cache_write_tokens": cache_write_tokens}

        self.input_tokens         = input_tokens
        self.output_tokens        = output_tokens
        self.input_tokens_details = type("Details", (), details)()


class StubResponse:
    """
    Description:
    Jedna atrapa odpowiedzi API Responses, z tym, co klient czyta. Zamiast modeli SDK, żeby testy
    nie zależały od ich konstruktorów.
    """

    def __init__(
        self,
        output_text:       str,                  # np. '{"problem": "Brak tonera"}'
        usage:             StubUsage,            # np. StubUsage(input_tokens=4820, …)
        model:             str = MODEL,          # np. "gpt-5.4-mini-2026-03-17"
        status:            str = "completed",    # np. "incomplete"
        incomplete_reason: str | None = None,    # np. "max_output_tokens"
    ):
        self.output_text        = output_text
        self.usage              = usage
        self.model              = model
        self.status             = status
        self.incomplete_details = type("Incomplete", (), {"reason": incomplete_reason})()


def make_client(
    model: str = MODEL,  # np. "gpt-6.1-sol"
) -> OpenAILLMClient:
    """
    Description:
    Buduje klienta z atrapą klucza. Nic tu nie sięga do sieci — klucz ma tylko przejść przez
    konstruktor.

    Example args:
        model="gpt-6.1-sol"

    Example result:
        OpenAILLMClient(model="gpt-6.1-sol")
    """
    return OpenAILLMClient(api_key=API_KEY, model=model, temperature=0.0)


# --- żądanie --------------------------------------------------------------------------------

def test_request_carries_the_prompt_and_the_system_prompt_apart() -> None:
    """Prompt i prompt systemowy → osobne pola `input` i `instructions`: w tym API prompt
    systemowy nie jest wiadomością."""
    request = make_client()._build_request("ZGŁOSZENIE 33644", "Jesteś parserem zgłoszeń.")

    assert request["model"]        == MODEL
    assert request["input"]        == "ZGŁOSZENIE 33644"
    assert request["instructions"] == "Jesteś parserem zgłoszeń."


def test_request_without_a_system_prompt_has_no_instructions() -> None:
    """Brak promptu systemowego → brak pola `instructions`, nie pusty tekst ani `None`."""
    assert "instructions" not in make_client()._build_request("ZGŁOSZENIE 33644", None)


def test_request_asks_the_provider_not_to_store_the_response() -> None:
    """Żądanie → `store: False`: to API domyślnie przechowuje odpowiedzi u dostawcy, a w prompcie
    są dane klienta."""
    assert make_client()._build_request("ZGŁOSZENIE 33644", None)["store"] is False


def test_request_caps_the_output() -> None:
    """Żądanie → sufit odpowiedzi w `max_output_tokens`; bez niego model rozumujący może
    zużyć dowolnie dużo."""
    assert make_client()._build_request("ZGŁOSZENIE 33644", None)["max_output_tokens"] > 0


@pytest.mark.parametrize("model", MODELS_WITH_TEMPERATURE)
def test_temperature_is_sent_to_models_that_accept_it(model: str) -> None:
    """Model z rodziny przyjmującej → `temperature` w żądaniu; dla parsowania determinizm ma
    znaczenie."""
    request = make_client(model)._build_request("ZGŁOSZENIE 33644", None)

    assert request["temperature"] == 0.0


@pytest.mark.parametrize("model", MODELS_WITHOUT_TEMPERATURE)
def test_temperature_is_withheld_from_models_that_reject_it(model: str) -> None:
    """Model odrzucający → brak `temperature` w żądaniu; API zwraca na nią 400, nie
    ostrzeżenie."""
    assert "temperature" not in make_client(model)._build_request("ZGŁOSZENIE 33644", None)


def test_the_temperature_lists_cover_the_whole_price_table() -> None:
    """Każdy model z cennika jest na jednej z dwóch list — nowy wiersz cennika bez sprawdzonej
    reguły `temperature` ma paść tutaj."""
    assert sorted(MODELS_WITH_TEMPERATURE + MODELS_WITHOUT_TEMPERATURE) == sorted(PRICES)


def test_dated_snapshot_inherits_its_family_rule() -> None:
    """Snapshot z datą → traktowany jak rodzina; API odsyła właśnie taki identyfikator."""
    assert "temperature" in make_client("gpt-5.4-mini-2026-03-17")._build_request("x", None)
    assert "temperature" not in make_client("o4-mini-2025-04-16")._build_request("x", None)


def test_unknown_model_family_gets_no_temperature() -> None:
    """Rodzina spoza listy przyjmujących → parametr pominięty: lista wymienia przyjmujące, więc
    model wydany po tym kodzie nie dostanie parametru, który odrzuci."""
    assert not "gpt-7".startswith(MODELS_ACCEPTING_TEMPERATURE)


# --- odpowiedź ------------------------------------------------------------------------------

def test_maps_usage_and_text() -> None:
    """Odpowiedź z tekstem → tekst, model i tokeny przepisane do LLMCompletion."""
    response = StubResponse(
        output_text = '{"problem": "Brak tonera"}',
        usage       = StubUsage(input_tokens=4820, output_tokens=640),
    )

    completion = make_client()._to_completion(response, elapsed_ms=3120.4)

    assert completion.text              == '{"problem": "Brak tonera"}'
    assert completion.model             == MODEL
    assert completion.prompt_tokens     == 4820
    assert completion.completion_tokens == 640
    assert completion.latency_ms        == 3120.4


def test_answer_without_text_raises() -> None:
    """Odpowiedź bez tekstu → LLMError ze statusem i powodem, nie pusty string."""
    # Tak API zgłasza model rozumujący, który zużył cały budżet na myślenie.
    response = StubResponse(
        output_text       = "",
        usage             = StubUsage(input_tokens=10, output_tokens=8000),
        status            = "incomplete",
        incomplete_reason = "max_output_tokens",
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "incomplete"        in str(exc.value)
    assert "max_output_tokens" in str(exc.value)


def test_reports_cost_for_the_call() -> None:
    """Wywołanie → cost_usd policzony ze stawek modelu, nie zero."""
    # 1 000 000 wejścia (0,75 USD) + 1 000 000 wyjścia (4,50 USD) przy stawkach gpt-5.4-mini.
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(5.25)


def test_cached_tokens_are_split_out_of_the_input_count() -> None:
    """Tokeny z cache siedzą w API wewnątrz `input_tokens` → własne pole, a `prompt_tokens` to
    samo świeże wejście; klasy rozłączne jak u Claude'a."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=5000, output_tokens=50, cached_tokens=4000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 1000
    assert completion.cache_read_tokens  == 4000
    assert completion.cache_write_tokens == 0


def test_cache_write_tokens_land_in_their_own_field() -> None:
    """Licznik zapisu do cache → własne pole, odjęty od świeżego wejścia: trzy klasy wejścia
    sumują się do tego, co podało API."""
    usage = StubUsage(
        input_tokens       = 5000,
        output_tokens      = 50,
        cached_tokens      = 3000,
        cache_write_tokens = 1500,
    )

    completion = make_client()._to_completion(
        StubResponse(output_text="ok", usage=usage), elapsed_ms=1.0
    )

    assert completion.prompt_tokens      == 500
    assert completion.cache_read_tokens  == 3000
    assert completion.cache_write_tokens == 1500


def test_cached_tokens_are_discounted_not_added() -> None:
    """Całe wejście odczytane z cache → 10% stawki wejścia; odczyt nie jest doliczany do pełnej
    ceny tych samych tokenów."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    # gpt-5.4-mini: 0,75 USD za milion wejścia, odczyt z cache za 0,10 tej stawki.
    assert completion.cost_usd == pytest.approx(0.75 * 0.10)


def test_cache_write_is_billed_at_its_own_rate() -> None:
    """Zapis do cache w rodzinie gpt-6 → 1,25 stawki wejścia zamiast zwykłej, nie obok niej."""
    # gpt-6.1-sol: wejście 2,00 USD za milion, zapis do cache 2,50.
    usage = StubUsage(input_tokens=1_000_000, output_tokens=0, cache_write_tokens=1_000_000)

    completion = make_client("gpt-6.1-sol")._to_completion(
        StubResponse(output_text="ok", usage=usage, model="gpt-6.1-sol"), elapsed_ms=1.0
    )

    assert completion.cost_usd == pytest.approx(2.50)


def test_cache_larger_than_input_does_not_go_negative() -> None:
    """Liczniki cache większe niż wejście → świeże wejście zero, nie ujemne; rachunek nie może
    wyjść poniżej zera, gdy liczniki się nie zgadzają."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=100, output_tokens=0, cached_tokens=5000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens == 0
    assert completion.cost_usd      >= 0


def test_missing_cache_details_default_to_zero() -> None:
    """Usage bez sekcji cache → zera, nie None w arytmetyce kosztu; całe wejście jest świeże."""
    class UsageWithoutDetails:
        input_tokens  = 100
        output_tokens = 50

    response = StubResponse(output_text="ok", usage=UsageWithoutDetails())

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 100
    assert completion.cache_read_tokens  == 0
    assert completion.cache_write_tokens == 0


def test_prices_the_model_that_actually_answered() -> None:
    """Model z odpowiedzi rozstrzyga o cenie — rachunek idzie za tym, co faktycznie policzyło."""
    # Klient prosi o gpt-5.4-mini (0,75/4,50), odpowiada gpt-5.4 (2,50/15,00).
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=1_000_000, output_tokens=0),
        model       = "gpt-5.4",
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.model    == "gpt-5.4"
    assert completion.cost_usd == pytest.approx(2.50)


# --- budowa klienta -------------------------------------------------------------------------

def test_empty_base_url_is_not_passed_as_empty_string() -> None:
    """Puste LLM_BASE_URL → klient buduje się i nie celuje w pusty adres."""
    # CLAUDE.md -> „Pułapki": docker compose wstawia pusty string zamiast braku, a
    # Client(base_url="") daje błąd połączenia zamiast czytelnego błędu configu.
    client = OpenAILLMClient(api_key=API_KEY, model=MODEL, base_url="")

    assert str(client._client.base_url).startswith("https://api.openai.com")
