import pytest

from app.engine_llm import LLMError
from app.engine_llm.client.openai import MODELS_REJECTING_TEMPERATURE, OpenAILLMClient

API_KEY = "sk-proj-test-key"
MODEL   = "gpt-5.4-mini"

# A reasoning model — the API rejects `temperature` on these with a 400.
MODEL_REJECTING_TEMPERATURE = "o4-mini"


class StubMessage:
    """
    Description:
    The message of a stubbed choice. `content` is None when the model wrote nothing, which is how
    the API reports a refusal or an exhausted reasoning budget.
    """

    def __init__(self, content: str | None):  # e.g. '{"problem": "Brak tonera"}'
        self.content = content


class StubChoice:
    """
    Description:
    One choice of a stubbed answer, carrying the two attributes the client reads.
    """

    def __init__(
        self,
        content:       str | None,       # e.g. '{"problem": "Brak tonera"}'
        finish_reason: str = "stop",     # e.g. "length"
    ):
        self.message       = StubMessage(content)
        self.finish_reason = finish_reason


class StubUsage:
    """
    Description:
    The usage counters of a stubbed answer. Cache counters are reported nested under
    `prompt_tokens_details`, so the stub mirrors that shape rather than flattening it.
    """

    def __init__(
        self,
        prompt_tokens:      int,      # e.g. 4820 — the whole input, cache counters included
        completion_tokens:  int,      # e.g. 640
        cached_tokens:      int = 0,  # e.g. 1830
        cache_write_tokens: int = 0,  # e.g. 1024
    ):
        details = {"cached_tokens": cached_tokens, "cache_write_tokens": cache_write_tokens}

        self.prompt_tokens         = prompt_tokens
        self.completion_tokens     = completion_tokens
        self.prompt_tokens_details = type("Details", (), details)()


class StubResponse:
    """
    Description:
    One stubbed answer from the Chat Completions API, carrying only what the client reads. Used
    instead of the SDK's own models so these tests stay independent of the SDK's constructors.
    """

    def __init__(
        self,
        choices: list[StubChoice],  # e.g. [StubChoice('{"problem": "…"}')]
        usage:   StubUsage,         # e.g. StubUsage(prompt_tokens=4820, completion_tokens=640)
        model:   str = MODEL,       # e.g. "gpt-5.4-mini"
    ):
        self.choices = choices
        self.usage   = usage
        self.model   = model


def make_client() -> OpenAILLMClient:
    """
    Description:
    Builds a client with a dummy key. Nothing here reaches the network — every test drives
    `_to_completion` directly, so the key only has to satisfy the constructor.

    Example args:
        (none)

    Example result:
        OpenAILLMClient(model="gpt-5.4-mini")
    """
    return OpenAILLMClient(api_key=API_KEY, model=MODEL)


def test_maps_usage_and_text():
    """Odpowiedź z tekstem → tekst, model i tokeny przepisane do LLMCompletion."""
    response = StubResponse(
        choices = [StubChoice('{"problem": "Brak tonera"}')],
        usage   = StubUsage(prompt_tokens=4820, completion_tokens=640),
    )

    completion = make_client()._to_completion(response, elapsed_ms=3120.4)

    assert completion.text              == '{"problem": "Brak tonera"}'
    assert completion.model             == MODEL
    assert completion.prompt_tokens     == 4820
    assert completion.completion_tokens == 640
    assert completion.latency_ms        == 3120.4


def test_answer_without_text_raises():
    """Odpowiedź z pustą treścią → LLMError z powodem zakończenia, nie pusty string."""
    # Tak API zgłasza odmowę albo model rozumujący, który zużył cały budżet na myślenie.
    response = StubResponse(
        choices = [StubChoice(None, finish_reason="length")],
        usage   = StubUsage(prompt_tokens=10, completion_tokens=8000),
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "length" in str(exc.value)


def test_answer_without_choices_raises():
    """Odpowiedź bez wariantów → LLMError, nie IndexError z wnętrza klienta."""
    response = StubResponse(choices=[], usage=StubUsage(prompt_tokens=10, completion_tokens=0))

    with pytest.raises(LLMError):
        make_client()._to_completion(response, elapsed_ms=1.0)


def test_reports_cost_for_the_call():
    """Wywołanie → cost_usd policzony ze stawek modelu, nie zero."""
    # 1 000 000 wejścia (0,75 USD) + 1 000 000 wyjścia (4,50 USD) przy stawkach gpt-5.4-mini.
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(5.25)


def test_cached_tokens_are_split_out_of_the_prompt_count():
    """Tokeny z cache siedzą w API wewnątrz prompt_tokens → własne pole, a prompt_tokens to
    samo świeże wejście; klasy rozłączne jak u Claude'a."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=5000, completion_tokens=50, cached_tokens=4000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 1000
    assert completion.cache_read_tokens  == 4000
    assert completion.cache_write_tokens == 0


def test_cache_write_tokens_land_in_their_own_field():
    """Licznik zapisu do cache → własne pole, odjęty od świeżego wejścia: trzy klasy wejścia
    sumują się do tego, co podało API."""
    usage = StubUsage(
        prompt_tokens      = 5000,
        completion_tokens  = 50,
        cached_tokens      = 3000,
        cache_write_tokens = 1500,
    )

    completion = make_client()._to_completion(
        StubResponse(choices=[StubChoice("ok")], usage=usage), elapsed_ms=1.0
    )

    assert completion.prompt_tokens      == 500
    assert completion.cache_read_tokens  == 3000
    assert completion.cache_write_tokens == 1500


def test_cached_tokens_are_discounted_not_added():
    """Całe wejście odczytane z cache → 10% stawki wejścia; odczyt nie jest doliczany do pełnej
    ceny tych samych tokenów."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=1_000_000, completion_tokens=0, cached_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    # gpt-5.4-mini: 0,75 USD za milion wejścia, odczyt z cache za 0,10 tej stawki.
    assert completion.cost_usd == pytest.approx(0.75 * 0.10)


def test_cache_write_is_billed_at_its_own_rate():
    """Zapis do cache w rodzinie gpt-6 → 1,25 stawki wejścia zamiast zwykłej, nie obok niej."""
    # gpt-6.1-sol: wejście 2,00 USD za milion, zapis do cache 2,50.
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(
            prompt_tokens      = 1_000_000,
            completion_tokens  = 0,
            cache_write_tokens = 1_000_000,
        ),
        model   = "gpt-6.1-sol",
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(2.50)


def test_cache_larger_than_prompt_does_not_go_negative():
    """Liczniki cache większe niż prompt → świeże wejście zero, nie ujemne; rachunek nie może
    wyjść poniżej zera, gdy liczniki się nie zgadzają."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=100, completion_tokens=0, cached_tokens=5000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens == 0
    assert completion.cost_usd      >= 0


def test_missing_cache_details_default_to_zero():
    """Usage bez sekcji cache → zera, nie None w arytmetyce kosztu; całe wejście jest świeże."""
    class UsageWithoutDetails:
        prompt_tokens     = 100
        completion_tokens = 50

    response = StubResponse(choices=[StubChoice("ok")], usage=UsageWithoutDetails())

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 100
    assert completion.cache_read_tokens  == 0
    assert completion.cache_write_tokens == 0


def test_temperature_is_sent_to_models_that_accept_it():
    """Model zwykły → temperature w żądaniu; dla parsowania determinizm ma znaczenie."""
    client = OpenAILLMClient(api_key=API_KEY, model=MODEL, temperature=0.0)

    assert client._accepts_temperature


def test_temperature_is_withheld_from_reasoning_models():
    """Model rozumujący → temperature pominięte; API zwraca na nie 400, nie ostrzeżenie."""
    # Zweryfikowane na żywym API 2026-08-02: `temperature=0` do o4-mini daje
    # 400 „Unsupported value: 'temperature' does not support 0 with this model".
    client = OpenAILLMClient(api_key=API_KEY, model=MODEL_REJECTING_TEMPERATURE)

    assert not client._accepts_temperature


def test_dated_snapshot_inherits_its_family_rule():
    """Snapshot z datą → traktowany jak rodzina; API odsyła właśnie taki identyfikator."""
    client = OpenAILLMClient(api_key=API_KEY, model="o4-mini-2025-04-16")

    assert not client._accepts_temperature


def test_unknown_model_family_keeps_temperature():
    """Model spoza listy odrzucających → parametr wysłany; lista wymienia odrzucające."""
    # Kierunek listy jest celowy i ODWROTNY niż przy Claude: tu zbiorem znanym i małym są modele
    # rozumujące, a każdy GPT z cennika parametr przyjmuje.
    assert not "gpt-6".startswith(MODELS_REJECTING_TEMPERATURE)


def test_prices_the_model_that_actually_answered():
    """Model z odpowiedzi rozstrzyga o cenie — rachunek idzie za tym, co faktycznie policzyło."""
    # Klient prosi o gpt-5.4-mini (0,75/4,50), odpowiada gpt-5.4 (2,50/15,00).
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=1_000_000, completion_tokens=0),
        model   = "gpt-5.4",
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.model    == "gpt-5.4"
    assert completion.cost_usd == pytest.approx(2.50)


def test_empty_base_url_is_not_passed_as_empty_string():
    """Puste LLM_BASE_URL → klient buduje się i nie celuje w pusty adres."""
    # CLAUDE.md -> „Pułapki": docker compose wstawia pusty string zamiast braku, a
    # Client(base_url="") daje błąd połączenia zamiast czytelnego błędu configu.
    client = OpenAILLMClient(api_key=API_KEY, model=MODEL, base_url="")

    assert str(client._client.base_url).startswith("https://api.openai.com")
