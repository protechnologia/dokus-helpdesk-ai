import pytest

from app.llm import LLMError
from app.llm.client_claude import MODELS_ACCEPTING_TEMPERATURE, ClaudeLLMClient

API_KEY = "sk-ant-test-key"
MODEL   = "claude-haiku-4-5"

# A model outside the accepting list — the API rejects `temperature` on these with a 400.
MODEL_WITHOUT_TEMPERATURE = "claude-sonnet-5"


class StubBlock:
    """
    Description:
    One content block of a stubbed answer. Mirrors the two attributes the client reads (`type`,
    `text`) so the mapping can be tested without constructing real SDK models.
    """

    def __init__(
        self,
        text:       str,           # e.g. '{"problem": "Brak tonera"}'
        block_type: str = "text",  # e.g. "text" or "thinking"
    ):
        self.text = text
        self.type = block_type


class StubUsage:
    """
    Description:
    The usage counters of a stubbed answer. Cache fields default to zero, which is what the API
    reports for a call that used no prompt caching.
    """

    def __init__(
        self,
        input_tokens:                int,      # e.g. 4820
        output_tokens:               int,      # e.g. 640
        cache_creation_input_tokens: int = 0,  # e.g. 1830
        cache_read_input_tokens:     int = 0,  # e.g. 1830
    ):
        self.input_tokens                = input_tokens
        self.output_tokens               = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens     = cache_read_input_tokens


class StubResponse:
    """
    Description:
    One stubbed answer from the Messages API, carrying only what the client actually reads. Used
    instead of the SDK's own models so these tests stay independent of the SDK's constructors.
    """

    def __init__(
        self,
        blocks:      list[StubBlock],  # e.g. [StubBlock('{"problem": "…"}')]
        usage:       StubUsage,        # e.g. StubUsage(input_tokens=4820, output_tokens=640)
        model:       str = MODEL,      # e.g. "claude-haiku-4-5"
        stop_reason: str = "end_turn", # e.g. "max_tokens"
    ):
        self.content     = blocks
        self.usage       = usage
        self.model       = model
        self.stop_reason = stop_reason


def make_client() -> ClaudeLLMClient:
    """
    Description:
    Builds a client with a dummy key. Nothing here reaches the network — every test drives
    `_to_completion` directly, so the key only has to satisfy the constructor.

    Example args:
        (none)

    Example result:
        ClaudeLLMClient(model="claude-haiku-4-5")
    """
    return ClaudeLLMClient(api_key=API_KEY, model=MODEL)


def test_maps_usage_and_text():
    """Odpowiedź z jednym blokiem tekstu → tekst, model i tokeny przepisane do LLMCompletion."""
    response = StubResponse(
        blocks = [StubBlock('{"problem": "Brak tonera"}')],
        usage  = StubUsage(input_tokens=4820, output_tokens=640),
    )

    completion = make_client()._to_completion(response, elapsed_ms=3120.4)

    assert completion.text              == '{"problem": "Brak tonera"}'
    assert completion.model             == MODEL
    assert completion.prompt_tokens     == 4820
    assert completion.completion_tokens == 640
    assert completion.latency_ms        == 3120.4


def test_joins_multiple_text_blocks():
    """Kilka bloków tekstu → sklejone w kolejności; czytanie content[0] gubiłoby resztę JSON-a."""
    response = StubResponse(
        blocks = [StubBlock('{"problem": '), StubBlock('"Brak tonera"}')],
        usage  = StubUsage(input_tokens=10, output_tokens=10),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.text == '{"problem": "Brak tonera"}'


def test_skips_non_text_blocks():
    """Blok nietekstowy przed tekstem → pomijany; content[0].text wywaliłby się na nim."""
    response = StubResponse(
        blocks = [
            StubBlock("rozważam wątek", block_type="thinking"),
            StubBlock('{"problem": "Brak tonera"}'),
        ],
        usage  = StubUsage(input_tokens=10, output_tokens=10),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.text == '{"problem": "Brak tonera"}'


def test_answer_without_text_raises():
    """Odpowiedź bez bloku tekstu → LLMError z powodem zatrzymania, nie pusty string."""
    response = StubResponse(
        blocks      = [],
        usage       = StubUsage(input_tokens=10, output_tokens=0),
        stop_reason = "max_tokens",
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "max_tokens" in str(exc.value)


def test_reports_cost_for_the_call():
    """Wywołanie → cost_usd policzony ze stawek modelu, nie zero."""
    # 1 000 000 wejścia (1 USD) + 1 000 000 wyjścia (5 USD) przy stawkach Haiku 4.5.
    response = StubResponse(
        blocks = [StubBlock("ok")],
        usage  = StubUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(6.00)


def test_cache_tokens_land_in_their_own_fields():
    """Tokeny cache → osobne pola LLMCompletion, nie doliczone do prompt_tokens."""
    response = StubResponse(
        blocks = [StubBlock("ok")],
        usage  = StubUsage(
            input_tokens                = 100,
            output_tokens               = 50,
            cache_creation_input_tokens = 1830,
            cache_read_input_tokens     = 920,
        ),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 100
    assert completion.cache_write_tokens == 1830
    assert completion.cache_read_tokens  == 920


def test_missing_cache_counters_default_to_zero():
    """Usage bez pól cache → zera, nie None w arytmetyce kosztu."""
    class UsageWithoutCache:
        input_tokens  = 100
        output_tokens = 50

    response = StubResponse(blocks=[StubBlock("ok")], usage=UsageWithoutCache())

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cache_write_tokens == 0
    assert completion.cache_read_tokens  == 0


def test_temperature_is_sent_to_models_that_accept_it():
    """Model z listy → temperature w żądaniu; dla parsowania determinizm ma znaczenie."""
    client = ClaudeLLMClient(api_key=API_KEY, model=MODEL, temperature=0.0)

    assert client._accepts_temperature


def test_temperature_is_withheld_from_models_that_reject_it():
    """Model spoza listy → temperature pominięte; API zwraca na nie 400, nie ostrzeżenie."""
    # Zweryfikowane na żywym API 2026-08-01: `temperature` do Sonnet 5 daje
    # 400 invalid_request_error „temperature is deprecated for this model".
    client = ClaudeLLMClient(api_key=API_KEY, model=MODEL_WITHOUT_TEMPERATURE)

    assert not client._accepts_temperature


def test_dated_snapshot_inherits_its_family_rule():
    """Snapshot z datą → traktowany jak rodzina; API odsyła właśnie taki identyfikator."""
    client = ClaudeLLMClient(api_key=API_KEY, model="claude-haiku-4-5-20251001")

    assert client._accepts_temperature


def test_unknown_model_family_withholds_temperature():
    """Model spoza listy rodzin → parametr pominięty; lista wymienia akceptujące, nie odrzucające"""
    # Kierunek listy jest celowy: model wydany po tym buildzie domyślnie NIE dostaje parametru,
    # bo cicho zignorowany knob jest gorszy niż nigdy niewysłany.
    assert not "claude-przyszly-7".startswith(MODELS_ACCEPTING_TEMPERATURE)


def test_prices_the_model_that_actually_answered():
    """Model z odpowiedzi rozstrzyga o cenie — rachunek idzie za tym, co faktycznie policzyło."""
    # Klient prosi o Haiku (1/5 USD), odpowiada Sonnet (3/15 USD).
    response = StubResponse(
        blocks = [StubBlock("ok")],
        usage  = StubUsage(input_tokens=1_000_000, output_tokens=0),
        model  = "claude-sonnet-5",
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.model    == "claude-sonnet-5"
    assert completion.cost_usd == pytest.approx(3.00)
