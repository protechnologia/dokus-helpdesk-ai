import pytest

from app.engine_llm import LLMError
from app.engine_llm.client.claude import MODELS_ACCEPTING_TEMPERATURE, ClaudeLLMClient

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
    """Sprawdza, czy odpowiedź z jednym blokiem tekstu jest przepisywana na `LLMCompletion` bez
    zmian: tekst, nazwa modelu, 4820 tokenów wejścia, 640 tokenów wyjścia i czas wywołania trafiają
    do swoich pól.

    Wyłapuje pomylone pola przy przepisywaniu, na przykład tokeny wejścia zapisane jako wyjście:
    zużycie i koszt wywołania byłyby wtedy liczone ze złych liczb."""
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
    """Sprawdza, czy odpowiedź podzielona na dwa bloki tekstu wraca jako jeden tekst, sklejony
    w kolejności bloków.

    Wyłapuje klienta, który czyta tylko pierwszy blok: reszta JSON-a by przepadła i odpowiedzi nie
    dałoby się sparsować."""
    response = StubResponse(
        blocks = [StubBlock('{"problem": '), StubBlock('"Brak tonera"}')],
        usage  = StubUsage(input_tokens=10, output_tokens=10),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.text == '{"problem": "Brak tonera"}'


def test_skips_non_text_blocks():
    """Sprawdza, czy blok, który nie jest tekstem (tu blok myślenia `thinking` przed właściwą
    odpowiedzią), jest pomijany, a wynikiem jest sam tekst odpowiedzi.

    Wyłapuje klienta, który bierze pierwszy blok bez sprawdzania jego rodzaju: do wyniku trafiłyby
    rozważania modelu zamiast odpowiedzi, a na bloku bez pola tekstu klient by się wywrócił."""
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
    """Sprawdza, czy odpowiedź bez żadnego bloku tekstu kończy się wyjątkiem `LLMError`, a jego
    komunikat podaje powód zatrzymania modelu (tu `max_tokens`).

    Wyłapuje klienta, który oddaje wtedy pusty tekst: błąd wyszedłby dopiero przy parsowaniu, bez
    informacji, że modelowi skończył się limit odpowiedzi."""
    response = StubResponse(
        blocks      = [],
        usage       = StubUsage(input_tokens=10, output_tokens=0),
        stop_reason = "max_tokens",
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "max_tokens" in str(exc.value)


def test_reports_cost_for_the_call():
    """Sprawdza, czy koszt wywołania jest liczony ze stawek modelu: milion tokenów wejścia i milion
    tokenów wyjścia w Haiku 4.5 daje 6 USD (1 USD za wejście i 5 USD za wyjście).

    Wyłapuje koszt, który zostaje zerem albo jest liczony ze złej stawki: zapisane wydatki na
    model przestałyby odpowiadać rachunkowi od dostawcy."""
    # 1 000 000 wejścia (1 USD) + 1 000 000 wyjścia (5 USD) przy stawkach Haiku 4.5.
    response = StubResponse(
        blocks = [StubBlock("ok")],
        usage  = StubUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(6.00)


def test_cache_tokens_land_in_their_own_fields():
    """Sprawdza, czy tokeny zapisu do cache (1830) i odczytu z cache (920) trafiają do osobnych pól
    wyniku, a licznik zwykłego wejścia zostaje przy swoich 100 tokenach.

    Wyłapuje doliczenie tokenów cache do zwykłego wejścia albo zamianę zapisu z odczytem: każda
    z tych klas ma inną stawkę, więc koszt wyszedłby błędny."""
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
    """Sprawdza, czy przy zużyciu, w którym dostawca nie podał liczników cache, oba pola cache
    w wyniku mają wartość zero.

    Wyłapuje klienta, który wymaga tych liczników: wywróciłby się na odpowiedzi bez nich albo
    wpuścił `None` do rachunku kosztu."""
    class UsageWithoutCache:
        input_tokens  = 100
        output_tokens = 50

    response = StubResponse(blocks=[StubBlock("ok")], usage=UsageWithoutCache())

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cache_write_tokens == 0
    assert completion.cache_read_tokens  == 0


def test_temperature_is_sent_to_models_that_accept_it():
    """Sprawdza, czy klient zbudowany dla modelu Haiku 4.5 zapamiętuje, że ten model przyjmuje
    parametr `temperature`.

    Wyłapuje usunięcie tego modelu z listy przyjmujących: temperatura przestałaby iść w żądaniu,
    a przy parsowaniu zgłoszeń zależy nam na możliwie powtarzalnych odpowiedziach."""
    client = ClaudeLLMClient(api_key=API_KEY, model=MODEL, temperature=0.0)

    assert client._accepts_temperature


def test_temperature_is_withheld_from_models_that_reject_it():
    """Sprawdza, czy klient zbudowany dla modelu `claude-sonnet-5`, którego nie ma na liście
    przyjmujących, zapamiętuje, że parametru `temperature` nie wolno mu wysyłać.

    Wyłapuje wysyłanie temperatury do nowszych modeli: API odpowiada na nią błędem 400, a nie
    ostrzeżeniem, więc każde wywołanie takiego modelu by padało."""
    # Zweryfikowane na żywym API 2026-08-01: `temperature` do Sonnet 5 daje
    # 400 invalid_request_error „temperature is deprecated for this model".
    client = ClaudeLLMClient(api_key=API_KEY, model=MODEL_WITHOUT_TEMPERATURE)

    assert not client._accepts_temperature


def test_dated_snapshot_inherits_its_family_rule():
    """Sprawdza, czy nazwa modelu z datą wydania (`claude-haiku-4-5-20251001`) jest traktowana tak
    samo jak jej rodzina `claude-haiku-4-5`, czyli jako model przyjmujący `temperature`.

    Wyłapuje dopasowanie po dokładnej nazwie zamiast po jej początku: wersja z datą, a taki
    identyfikator odsyła samo API, przestałaby dostawać temperaturę."""
    client = ClaudeLLMClient(api_key=API_KEY, model="claude-haiku-4-5-20251001")

    assert client._accepts_temperature


def test_unknown_model_family_withholds_temperature():
    """Sprawdza, czy zmyślona nazwa modelu `claude-przyszly-7` nie pasuje do listy rodzin
    przyjmujących `temperature`, czyli model nieznanej rodziny domyślnie tego parametru nie dostaje.

    Wyłapuje wpis na liście tak szeroki, że pasuje do każdej nazwy (na przykład samo `claude-`):
    model wydany po tym kodzie dostawałby parametr, którego może nie obsługiwać."""
    # Kierunek listy jest celowy: model wydany po tym buildzie domyślnie NIE dostaje parametru,
    # bo cicho zignorowany knob jest gorszy niż nigdy niewysłany.
    assert not "claude-przyszly-7".startswith(MODELS_ACCEPTING_TEMPERATURE)


def test_prices_the_model_that_actually_answered():
    """Sprawdza, czy koszt jest liczony według modelu podanego w odpowiedzi, a nie tego, o który
    klient prosił: klient ustawiony na Haiku dostaje odpowiedź od `claude-opus-5-5` i milion tokenów
    wejścia kosztuje 4 USD, a nie 1 USD.

    Wyłapuje wycenę po modelu z konfiguracji: gdy odpowie inny model, zapisany koszt rozjechałby
    się z tym, co naprawdę naliczył dostawca."""
    # Klient prosi o Haiku (1/5 USD), odpowiada Opus 5.5 (4/20 USD).
    response = StubResponse(
        blocks = [StubBlock("ok")],
        usage  = StubUsage(input_tokens=1_000_000, output_tokens=0),
        model  = "claude-opus-5-5",
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.model    == "claude-opus-5-5"
    assert completion.cost_usd == pytest.approx(4.00)


def test_every_request_asks_for_prompt_caching():
    """Sprawdza, czy żądanie do Claude'a ma na górnym poziomie pole `cache_control` o wartości
    `{"type": "ephemeral"}`, którym prosimy dostawcę o cache promptu.

    Wyłapuje zgubienie tego pola: w pętli z narzędziami cała dotychczasowa rozmowa byłaby wtedy
    w każdej turze liczona po pełnej stawce, a nie po ułamku stawki za odczyt z cache."""
    request = make_client()._build_request("ZGŁOSZENIE 41002…", system="Jesteś parserem.")

    assert request["cache_control"] == {"type": "ephemeral"}


def test_the_request_carries_the_system_prompt_at_the_top_level():
    """Sprawdza, czy prompt systemowy idzie w żądaniu jako osobne pole `system`, a na liście
    wiadomości jest tylko wiadomość użytkownika. Gdy promptu systemowego nie ma, żądanie nie ma pola
    `system` wcale.

    Wyłapuje prompt systemowy wysłany jako wiadomość, bo model czytałby go wtedy jak tekst
    użytkownika, oraz pole `system` wysłane z wartością `None`, którą API odrzuca."""
    client = make_client()

    with_system    = client._build_request("treść", system="Jesteś parserem.")
    without_system = client._build_request("treść", system=None)

    assert with_system["system"]   == "Jesteś parserem."
    assert with_system["messages"] == [{"role": "user", "content": "treść"}]
    assert "system" not in without_system


def test_the_request_sends_temperature_only_where_it_is_accepted():
    """Sprawdza, czy pole `temperature` trafia do żądania tylko dla modelu, który je przyjmuje: dla
    Haiku 4.5 żądanie ma `temperature` równe 0.0, a dla `claude-sonnet-5` tego pola nie ma.

    Wyłapuje żądanie składane bez oglądania się na model: nowszy model odpowiada na `temperature`
    błędem 400, a Haiku bez tego pola nie dostałby ustawionej temperatury."""
    accepting = ClaudeLLMClient(api_key=API_KEY, model=MODEL, temperature=0.0)
    refusing  = ClaudeLLMClient(api_key=API_KEY, model=MODEL_WITHOUT_TEMPERATURE)

    assert accepting._build_request("treść", None)["temperature"] == 0.0
    assert "temperature" not in refusing._build_request("treść", None)
