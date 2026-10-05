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
    """Sprawdza, czy w żądaniu do OpenAI tekst promptu idzie w polu `input`, a prompt systemowy
    w osobnym polu `instructions`, obok nazwy modelu.

    Wyłapuje zamianę tych pól albo zgubienie jednego z nich: w tym API prompt systemowy ma własne
    pole i nie jest wiadomością, więc bez niego model dostałby zgłoszenie bez instrukcji."""
    request = make_client()._build_request("ZGŁOSZENIE 33644", "Jesteś parserem zgłoszeń.")

    assert request["model"]        == MODEL
    assert request["input"]        == "ZGŁOSZENIE 33644"
    assert request["instructions"] == "Jesteś parserem zgłoszeń."


def test_request_without_a_system_prompt_has_no_instructions() -> None:
    """Sprawdza, czy żądanie złożone bez promptu systemowego w ogóle nie ma pola `instructions`.

    Wyłapuje pole `instructions` wysyłane z pustym tekstem albo z `None`: brak promptu
    systemowego ma znaczyć brak pola, a nie pustą instrukcję dla modelu."""
    assert "instructions" not in make_client()._build_request("ZGŁOSZENIE 33644", None)


def test_request_asks_the_provider_not_to_store_the_response() -> None:
    """Sprawdza, czy żądanie do OpenAI ma pole `store` ustawione na `False`, czyli prosi dostawcę,
    żeby nie przechowywał odpowiedzi.

    Wyłapuje zgubienie tego pola: to API domyślnie przechowuje odpowiedzi u dostawcy, a w prompcie
    są dane klienta."""
    assert make_client()._build_request("ZGŁOSZENIE 33644", None)["store"] is False


def test_request_caps_the_output() -> None:
    """Sprawdza, czy żądanie do OpenAI ma w polu `max_output_tokens` dodatni limit długości
    odpowiedzi.

    Wyłapuje żądanie bez limitu: model rozumujący mógłby wtedy zużyć dowolnie dużo tokenów, za
    które płacimy."""
    assert make_client()._build_request("ZGŁOSZENIE 33644", None)["max_output_tokens"] > 0


@pytest.mark.parametrize("model", MODELS_WITH_TEMPERATURE)
def test_temperature_is_sent_to_models_that_accept_it(model: str) -> None:
    """Sprawdza, czy dla każdego z pięciu modeli z rodzin `gpt-5.4` i `gpt-4.1` żądanie niesie pole
    `temperature` z ustawioną wartością 0.0.

    Wyłapuje model, który wypadł z listy przyjmujących: przestałby dostawać temperaturę, a przy
    parsowaniu zgłoszeń zależy nam na możliwie powtarzalnych odpowiedziach."""
    request = make_client(model)._build_request("ZGŁOSZENIE 33644", None)

    assert request["temperature"] == 0.0


@pytest.mark.parametrize("model", MODELS_WITHOUT_TEMPERATURE)
def test_temperature_is_withheld_from_models_that_reject_it(model: str) -> None:
    """Sprawdza, czy dla każdego z dziewięciu modeli, które nie przyjmują `temperature` (rodziny
    `gpt-6`, `gpt-5.6`, `gpt-5.5` i `o4-mini`), żądanie nie ma tego pola.

    Wyłapuje wysłanie temperatury takiemu modelowi: API odpowiada na nią błędem 400, a nie
    ostrzeżeniem, więc każde wywołanie by padało."""
    assert "temperature" not in make_client(model)._build_request("ZGŁOSZENIE 33644", None)


def test_the_temperature_lists_cover_the_whole_price_table() -> None:
    """Sprawdza, czy dwie listy modeli z tego pliku, przyjmujących `temperature` i odrzucających ją,
    razem pokrywają dokładnie wszystkie modele z cennika OpenAI, każdy raz.

    Wyłapuje nowy wiersz cennika dodany bez sprawdzenia, czy model przyjmuje `temperature`: taki
    model nie byłby objęty żadnym z testów tej reguły."""
    assert sorted(MODELS_WITH_TEMPERATURE + MODELS_WITHOUT_TEMPERATURE) == sorted(PRICES)


def test_dated_snapshot_inherits_its_family_rule() -> None:
    """Sprawdza, czy nazwa modelu z datą wydania dziedziczy regułę swojej rodziny:
    `gpt-5.4-mini-2026-03-17` dostaje `temperature` w żądaniu, a `o4-mini-2025-04-16` nie.

    Wyłapuje regułę dopasowaną do dokładnej nazwy zamiast do jej początku: wersja z datą, a taki
    identyfikator odsyła samo API, byłaby traktowana inaczej niż jej rodzina."""
    assert "temperature" in make_client("gpt-5.4-mini-2026-03-17")._build_request("x", None)
    assert "temperature" not in make_client("o4-mini-2025-04-16")._build_request("x", None)


def test_unknown_model_family_gets_no_temperature() -> None:
    """Sprawdza, czy zmyślona nazwa modelu `gpt-7` nie pasuje do listy rodzin przyjmujących
    `temperature`, czyli model nieznanej rodziny domyślnie tego parametru nie dostaje.

    Wyłapuje wpis na liście tak szeroki, że pasuje do każdej nazwy (na przykład samo `gpt-`):
    model wydany po tym kodzie dostawałby parametr, na który może odpowiedzieć błędem."""
    assert not "gpt-7".startswith(MODELS_ACCEPTING_TEMPERATURE)


# --- odpowiedź ------------------------------------------------------------------------------

def test_maps_usage_and_text() -> None:
    """Sprawdza, czy odpowiedź z tekstem jest przepisywana na `LLMCompletion` bez zmian: tekst,
    nazwa modelu, 4820 tokenów wejścia, 640 tokenów wyjścia i czas wywołania trafiają do swoich pól.

    Wyłapuje pomylone pola przy przepisywaniu, na przykład tokeny wejścia zapisane jako wyjście:
    zużycie i koszt wywołania byłyby wtedy liczone ze złych liczb."""
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
    """Sprawdza, czy odpowiedź z pustym tekstem kończy się wyjątkiem `LLMError`, a jego komunikat
    podaje status odpowiedzi (`incomplete`) i powód (`max_output_tokens`).

    Wyłapuje klienta, który oddaje wtedy pusty tekst: błąd wyszedłby dopiero przy parsowaniu, bez
    informacji, że model zużył cały limit odpowiedzi, zanim cokolwiek napisał."""
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
    """Sprawdza, czy koszt wywołania jest liczony ze stawek modelu: milion tokenów wejścia i milion
    tokenów wyjścia w `gpt-5.4-mini` daje 5,25 USD (0,75 USD za wejście i 4,50 USD za wyjście).

    Wyłapuje koszt, który zostaje zerem albo jest liczony ze złej stawki: zapisane wydatki na
    model przestałyby odpowiadać rachunkowi od dostawcy."""
    # 1 000 000 wejścia (0,75 USD) + 1 000 000 wyjścia (4,50 USD) przy stawkach gpt-5.4-mini.
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == pytest.approx(5.25)


def test_cached_tokens_are_split_out_of_the_input_count() -> None:
    """Sprawdza, czy tokeny odczytane z cache są wyjmowane z licznika wejścia: dostawca podaje 5000
    tokenów wejścia, w tym 4000 z cache, a wynik ma 1000 tokenów świeżego wejścia i 4000 tokenów
    odczytu z cache.

    Wyłapuje policzenie tych samych tokenów dwa razy, raz jako wejście i raz jako odczyt z cache:
    koszt wyszedłby zawyżony, a liczniki znaczyłyby co innego niż u Claude'a."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=5000, output_tokens=50, cached_tokens=4000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 1000
    assert completion.cache_read_tokens  == 4000
    assert completion.cache_write_tokens == 0


def test_cache_write_tokens_land_in_their_own_field() -> None:
    """Sprawdza, czy tokeny zapisu do cache dostają własne pole i też są odejmowane od wejścia:
    z 5000 tokenów wejścia, w tym 3000 odczytu i 1500 zapisu, zostaje 500 tokenów świeżego wejścia.

    Wyłapuje zgubienie licznika zapisu albo zostawienie go w świeżym wejściu: trzy klasy wejścia
    przestałyby się sumować do liczby podanej przez dostawcę, a zapis byłby liczony po złej
    stawce."""
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
    """Sprawdza, czy wejście odczytane w całości z cache kosztuje ułamek zwykłej stawki: milion
    takich tokenów w `gpt-5.4-mini` to 10% z 0,75 USD, czyli 0,075 USD.

    Wyłapuje doliczanie odczytu z cache do pełnej ceny tych samych tokenów: zapisany koszt byłby
    wtedy wielokrotnie wyższy od rachunku dostawcy."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    # gpt-5.4-mini: 0,75 USD za milion wejścia, odczyt z cache za 0,10 tej stawki.
    assert completion.cost_usd == pytest.approx(0.75 * 0.10)


def test_cache_write_is_billed_at_its_own_rate() -> None:
    """Sprawdza, czy zapis do cache jest liczony po własnej stawce: milion tokenów zapisu
    w `gpt-6.1-sol` kosztuje 2,50 USD, czyli 1,25 stawki wejścia (2,00 USD).

    Wyłapuje zapis liczony po zwykłej stawce wejścia albo doliczany obok niej: koszt wyszedłby
    2,00 albo 4,50 USD zamiast 2,50 USD."""
    # gpt-6.1-sol: wejście 2,00 USD za milion, zapis do cache 2,50.
    usage = StubUsage(input_tokens=1_000_000, output_tokens=0, cache_write_tokens=1_000_000)

    completion = make_client("gpt-6.1-sol")._to_completion(
        StubResponse(output_text="ok", usage=usage, model="gpt-6.1-sol"), elapsed_ms=1.0
    )

    assert completion.cost_usd == pytest.approx(2.50)


def test_cache_larger_than_input_does_not_go_negative() -> None:
    """Sprawdza, czy przy licznikach, które się nie zgadzają (100 tokenów wejścia, a 5000
    odczytanych z cache), świeże wejście wynosi zero, a koszt nie jest ujemny.

    Wyłapuje odejmowanie bez dolnej granicy: ujemna liczba tokenów dałaby ujemny koszt, który
    zaniżałby sumę wydatków."""
    response = StubResponse(
        output_text = "ok",
        usage       = StubUsage(input_tokens=100, output_tokens=0, cached_tokens=5000),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens == 0
    assert completion.cost_usd      >= 0


def test_missing_cache_details_default_to_zero() -> None:
    """Sprawdza, czy przy zużyciu, w którym dostawca nie podał szczegółów cache, oba pola cache
    mają wartość zero, a całe 100 tokenów wejścia jest liczone jako świeże.

    Wyłapuje klienta, który wymaga tych szczegółów: wywróciłby się na odpowiedzi bez nich albo
    wpuścił `None` do rachunku kosztu."""
    class UsageWithoutDetails:
        input_tokens  = 100
        output_tokens = 50

    response = StubResponse(output_text="ok", usage=UsageWithoutDetails())

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.prompt_tokens      == 100
    assert completion.cache_read_tokens  == 0
    assert completion.cache_write_tokens == 0


def test_prices_the_model_that_actually_answered() -> None:
    """Sprawdza, czy koszt jest liczony według modelu podanego w odpowiedzi, a nie tego, o który
    klient prosił: klient ustawiony na `gpt-5.4-mini` dostaje odpowiedź od `gpt-5.4` i milion
    tokenów wejścia kosztuje 2,50 USD, a nie 0,75 USD.

    Wyłapuje wycenę po modelu z konfiguracji: gdy odpowie inny model, zapisany koszt rozjechałby
    się z tym, co naprawdę naliczył dostawca."""
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
    """Sprawdza, czy klient zbudowany z pustym tekstem w miejscu adresu bazowego łączy się
    z domyślnym adresem OpenAI, `https://api.openai.com`.

    Wyłapuje przekazanie pustego adresu do SDK: docker compose wstawia pusty tekst w miejsce
    nieustawionej zmiennej adresu (`LLM_GENERATION_BASE_URL`), a klient kończyłby wtedy każde
    wywołanie błędem połączenia."""
    # CLAUDE.md -> „Pułapki": docker compose wstawia pusty string zamiast braku, a
    # Client(base_url="") daje błąd połączenia zamiast czytelnego błędu configu.
    client = OpenAILLMClient(api_key=API_KEY, model=MODEL, base_url="")

    assert str(client._client.base_url).startswith("https://api.openai.com")
