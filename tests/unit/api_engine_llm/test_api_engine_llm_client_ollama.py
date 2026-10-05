from pathlib import Path

import pytest

from app.engine_llm import LLMConfigError, LLMError
from app.engine_llm.client import ollama as client_ollama
from app.engine_llm.client.ollama import OllamaLLMClient

MODEL = "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"


class StubMessage:
    """
    Description:
    The message of a stubbed choice. `content` is None when the model wrote nothing.
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
        content:       str | None,    # e.g. '{"problem": "Brak tonera"}'
        finish_reason: str = "stop",  # e.g. "length"
    ):
        self.message       = StubMessage(content)
        self.finish_reason = finish_reason


class StubUsage:
    """
    Description:
    The usage counters of a stubbed answer. No cache fields — a local runner reports none, which is
    exactly what these tests need to pin down.
    """

    def __init__(
        self,
        prompt_tokens:     int,  # e.g. 6200
        completion_tokens: int,  # e.g. 310
    ):
        self.prompt_tokens     = prompt_tokens
        self.completion_tokens = completion_tokens


class StubResponse:
    """
    Description:
    One stubbed answer from the local server, carrying only what the client reads.
    """

    def __init__(
        self,
        choices: list[StubChoice],  # e.g. [StubChoice('{"problem": "…"}')]
        usage:   StubUsage,         # e.g. StubUsage(prompt_tokens=6200, completion_tokens=310)
        model:   str = MODEL,       # e.g. "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    ):
        self.choices = choices
        self.usage   = usage
        self.model   = model


# Przedrostek zmiennych roli, której klient służy w tych testach — nim nazywa zmienne w błędach.
ENV_PREFIX = "LLM_ANONYMIZATION_"


def make_client() -> OllamaLLMClient:
    """
    Description:
    Builds a client pointed at the default local address. Nothing here reaches the network — every
    test drives `_to_completion` directly.

    Example args:
        (none)

    Example result:
        OllamaLLMClient(model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0")
    """
    return OllamaLLMClient(model=MODEL, env_prefix=ENV_PREFIX)


def test_maps_usage_and_text():
    """Sprawdza, czy odpowiedź lokalnego modelu jest przepisywana na `LLMCompletion` bez zmian:
    tekst, nazwa modelu, 6200 tokenów wejścia, 310 tokenów wyjścia i czas wywołania trafiają do
    swoich pól.

    Wyłapuje pomylone pola przy przepisywaniu, na przykład tokeny wejścia zapisane jako wyjście:
    zapisane zużycie i czas wywołania przestałyby odpowiadać temu, co podał serwer."""
    response = StubResponse(
        choices = [StubChoice('{"problem": "Brak tonera"}')],
        usage   = StubUsage(prompt_tokens=6200, completion_tokens=310),
    )

    completion = make_client()._to_completion(response, elapsed_ms=384000.0)

    assert completion.text              == '{"problem": "Brak tonera"}'
    assert completion.model             == MODEL
    assert completion.prompt_tokens     == 6200
    assert completion.completion_tokens == 310
    assert completion.latency_ms        == 384000.0


def test_local_run_is_free():
    """Sprawdza, czy wywołanie lokalnego modelu ma koszt równy zero, niezależnie od liczby tokenów
    (tu 6200 wejścia i 310 wyjścia).

    Wyłapuje naliczanie lokalnemu modelowi ceny za tokeny: na własnym sprzęcie płacimy za prąd,
    nie za tokeny, więc zestawienie kosztów pokazywałoby wydatek, którego nie było."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=6200, completion_tokens=310),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == 0.0


def test_any_model_name_is_accepted():
    """Sprawdza, czy klienta lokalnego modelu da się zbudować z dowolną nazwą modelu, także taką,
    której nie ma w żadnym cenniku (`jakis/nowy-model:latest`).

    Wyłapuje przeniesienie tu sprawdzenia cennika z klientów chmurowych: lokalny model nie ma
    ceny, więc odmowa przy nieznanej nazwie blokowałaby przebieg bez powodu."""
    # Odwrotnie niż w klientach chmurowych, gdzie nieznany model to LLMConfigError: tu nie ma
    # rachunku, który mógłby zaskoczyć.
    assert OllamaLLMClient(model="jakis/nowy-model:latest", env_prefix=ENV_PREFIX)


def test_cache_fields_stay_at_zero():
    """Sprawdza, czy pola odczytu i zapisu cache w wyniku mają wartość zero, skoro lokalny serwer
    nie podaje żadnych liczników cache.

    Wyłapuje klienta, który wpisuje tam cokolwiek innego: zmyślona liczba wyglądałaby
    w zestawieniu zużycia jak prawdziwy pomiar."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=100, completion_tokens=50),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cache_read_tokens  == 0
    assert completion.cache_write_tokens == 0


def test_answer_without_text_raises():
    """Sprawdza, czy odpowiedź bez treści kończy się wyjątkiem `LLMError`, a jego komunikat podaje
    powód zakończenia (tu `length`, czyli model doszedł do limitu długości odpowiedzi).

    Wyłapuje klienta, który oddaje wtedy pusty tekst: błąd wyszedłby dopiero przy parsowaniu,
    a po długim lokalnym przebiegu nie byłoby wiadomo, dlaczego brakuje wyniku."""
    response = StubResponse(
        choices = [StubChoice(None, finish_reason="length")],
        usage   = StubUsage(prompt_tokens=10, completion_tokens=4000),
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "length" in str(exc.value)


def test_answer_without_choices_raises():
    """Sprawdza, czy odpowiedź, w której serwer nie zwrócił ani jednego wariantu odpowiedzi, kończy
    się wyjątkiem `LLMError`.

    Wyłapuje sięganie po pierwszy wariant bez sprawdzenia, czy istnieje: zamiast naszego błędu
    modelu poleciałby `IndexError` z wnętrza klienta, który nie mówi, co się stało."""
    response = StubResponse(choices=[], usage=StubUsage(prompt_tokens=10, completion_tokens=0))

    with pytest.raises(LLMError):
        make_client()._to_completion(response, elapsed_ms=1.0)


def test_default_timeout_fits_a_cpu_run():
    """Sprawdza, czy domyślny limit czasu klienta lokalnego modelu wynosi co najmniej 600 sekund.

    Wyłapuje powrót do 60 sekund z klientów chmurowych: na samym procesorze model pisze około
    jednego tokenu na sekundę, więc każde wywołanie byłoby przerywane przed końcem."""
    # Zmierzone 2026-08-02: ~1 token/s na 4.5B bez GPU, więc domyślne 60 s z klientów chmurowych
    # przerwałoby każde wywołanie.
    assert make_client()._client.timeout >= 600


def test_points_at_the_local_server_by_default():
    """Sprawdza, czy klient zbudowany bez podanego adresu łączy się z lokalnym serwerem Ollamy na
    porcie 11434.

    Wyłapuje zmianę domyślnego adresu: 11434 to stały port tego narzędzia, więc klient bez
    konfiguracji przestałby trafiać do serwera uruchomionego na tej samej maszynie."""
    assert "11434" in str(make_client()._client.base_url)


def test_context_window_is_stated_explicitly():
    """Sprawdza, czy klient zbudowany bez podanego rozmiaru okna kontekstu przyjmuje 8192 tokeny.

    Wyłapuje zmianę tej wartości domyślnej albo klienta bez żadnego rozmiaru okna: bez niego nie
    ma jak odrzucić za długiego zgłoszenia, a Ollama ucina nadmiar bez ostrzeżenia (jej własne okno
    domyślne to 2048 tokenów)."""
    assert make_client()._num_ctx == 8192


def test_input_longer_than_the_window_is_refused():
    """Sprawdza, czy wejście o długości 87 tysięcy znaków, które nie zmieści się w oknie 8192
    tokenów, jest odrzucane wyjątkiem `LLMError` z komunikatem „za długie”, bez wysyłania do modelu.

    Wyłapuje przepuszczenie za długiego wątku: serwer uciąłby go po cichu, a karta zgłoszenia
    powstałaby z części wątku i wyglądała na kompletną."""
    # Zgłoszenie 33319 ma 87 tys. znaków; przy oknie 8192 tokenów nie ma szans się zmieścić.
    with pytest.raises(LLMError, match="za długie"):
        make_client()._reject_if_too_long("x" * 87_000, system=None)


def test_the_refusal_names_the_settings_to_change():
    """Sprawdza, czy komunikat odmowy przy za długim wejściu wymienia obie zmienne konfiguracji, od
    których zależy limit, z przedrostkiem roli, której klient służy: `LLM_ANONYMIZATION_NUM_CTX`
    i `LLM_ANONYMIZATION_MAX_OUTPUT_TOKENS`.

    Wyłapuje komunikat bez tych nazw albo z nazwą zmiennej innej roli: osoba uruchamiająca
    przebieg nie wiedziałaby, które ustawienie podnieść, albo podniosłaby nie to."""
    with pytest.raises(LLMError) as exc:
        make_client()._reject_if_too_long("x" * 87_000, system=None)

    assert "LLM_ANONYMIZATION_NUM_CTX"           in str(exc.value)
    assert "LLM_ANONYMIZATION_MAX_OUTPUT_TOKENS" in str(exc.value)


def test_system_prompt_counts_towards_the_limit():
    """Sprawdza, czy do limitu długości wejścia liczy się także prompt systemowy: zgłoszenie
    o 10 znaków krótsze od limitu przechodzi samo, a razem z promptem systemowym o 100 znakach jest
    odrzucane.

    Wyłapuje liczenie samego zgłoszenia: prompt systemowy zajmuje to samo okno kontekstu, więc
    wejście uznane za mieszczące się zostałoby przez serwer ucięte."""
    client = make_client()
    tuz_pod_limitem = "x" * (client._max_prompt_chars - 10)

    client._reject_if_too_long(tuz_pod_limitem, system=None)          # samo zgłoszenie: mieści się

    with pytest.raises(LLMError):                                      # z promptem: już nie
        client._reject_if_too_long(tuz_pod_limitem, system="y" * 100)


def test_input_that_fits_passes_quietly():
    """Sprawdza, czy krótkie zgłoszenie z krótkim promptem systemowym przechodzi sprawdzenie
    długości bez wyjątku.

    Wyłapuje sprawdzenie, które odrzuca także wejście mieszczące się w oknie: żadne zgłoszenie
    nie dotarłoby wtedy do modelu."""
    assert make_client()._reject_if_too_long("krótkie zgłoszenie", system="prompt") is None


def test_answer_filling_the_whole_window_is_rejected():
    """Sprawdza, czy odpowiedź, przy której serwer naliczył 8192 tokeny wejścia, czyli całe okno
    kontekstu, jest odrzucana wyjątkiem `LLMError` z komunikatem o uciętym wątku.

    Wyłapuje przyjęcie takiej odpowiedzi: wejście wypełniające całe okno prawie na pewno zostało
    ucięte, a na końcu wątku zwykle stoi rozwiązanie, więc karta powstałaby bez niego."""
    # Druga linia obrony: sprawdzenie długości działa na SZACUNKU, to na faktycznym zużyciu.
    response = StubResponse(
        choices = [StubChoice('{"problem": "…"}')],
        usage   = StubUsage(prompt_tokens=8192, completion_tokens=100),
    )

    with pytest.raises(LLMError, match="ucięty"):
        make_client()._to_completion(response, elapsed_ms=1.0)


def test_answer_budget_larger_than_the_window_fails_at_build_time():
    """Sprawdza, czy klienta nie da się zbudować, gdy limit odpowiedzi jest równy oknu kontekstu
    (oba po 1000 tokenów): budowa kończy się wyjątkiem `LLMConfigError`, który wymienia
    `LLM_ANONYMIZATION_MAX_OUTPUT_TOKENS`.

    Wyłapuje brak tego sprawdzenia przy starcie: na zgłoszenie nie zostawałoby w oknie żadne
    miejsce i każde wywołanie padałoby z błędem, który wygląda na problem z danymi, a nie
    z konfiguracją."""
    with pytest.raises(LLMConfigError, match="LLM_ANONYMIZATION_MAX_OUTPUT_TOKENS"):
        OllamaLLMClient(model=MODEL, env_prefix=ENV_PREFIX, num_ctx=1000, max_output_tokens=1000)


def test_answer_budget_is_carved_out_of_the_window():
    """Sprawdza, czy limit znaków na wejście jest mniejszy niż całe okno kontekstu przeliczone na
    znaki: przy oknie 8192 tokenów i 1500 tokenach zarezerwowanych na odpowiedź limit wychodzi
    poniżej 8192 × 3 znaków.

    Wyłapuje limit liczony z całego okna, bez odjęcia miejsca na odpowiedź: wejście i odpowiedź
    razem nie zmieściłyby się wtedy w oknie."""
    client = OllamaLLMClient(
        model             = MODEL,
        env_prefix        = ENV_PREFIX,
        num_ctx           = 8192,
        max_output_tokens = 1500,
    )

    assert client._max_prompt_chars < 8192 * 3


def test_num_ctx_is_not_sent_in_the_request():
    """Sprawdza, czy w kodzie klienta lokalnego modelu, poza komentarzami, nie ma ani jednego
    użycia `extra_body`, czyli drogi, którą rozmiar okna kontekstu `num_ctx` trafiałby do żądania.

    Wyłapuje powrót `num_ctx` do żądania: Ollama go tam ignoruje, bo okno ustawia wyłącznie
    serwer, więc taki kod udawałby, że klient steruje oknem, choć niczego nie zmienia."""
    # Zmierzone 2026-08-02 na Ollamie 0.32.5: prompt ~18 tys. tokenów przeszedł w całości przy
    # żądaniu deklarującym okno 1024 — zarówno w surowym JSON-ie, jak i przez extra_body w SDK.
    # Okno ustawia wyłącznie serwer (OLLAMA_CONTEXT_LENGTH), więc `_num_ctx` służy TYLKO do
    # odrzucania za długiego wejścia po naszej stronie.
    source = Path(client_ollama.__file__).read_text(encoding="utf-8")
    code   = [line for line in source.splitlines() if not line.strip().startswith("#")]

    assert not [line for line in code if "extra_body" in line], (
        "num_ctx wrócił do żądania — Ollama go ignoruje (patrz komentarz przy DEFAULT_NUM_CTX)"
    )


def _answer(prompt_tokens: int) -> StubResponse:
    """
    Description:
    Builds a stubbed answer reporting the given input usage. Used by the truncation-ratio tests,
    where the only thing that matters is how many tokens the server claims to have read.

    Example args:
        prompt_tokens=16386

    Example result:
        StubResponse(choices=[StubChoice('{"problem": "…"}')], usage=StubUsage(16386, 17))
    """
    return StubResponse(
        choices = [StubChoice('{"problem": "…"}')],
        usage   = StubUsage(prompt_tokens=prompt_tokens, completion_tokens=17),
    )


def test_detects_truncation_even_when_the_window_is_misconfigured():
    """Sprawdza, czy klient odrzuca odpowiedź wyjątkiem `LLMError`, gdy serwer naliczył wyraźnie
    mniej tokenów, niż wynika z wysłanego tekstu: 16 386 tokenów przy 92 175 wysłanych znakach,
    choć w konfiguracji okno ma 32 768 tokenów.

    Wyłapuje ucięcie wejścia, którego nie widzą sprawdzenia oparte na `NUM_CTX`: gdy serwer
    działa z mniejszym oknem niż wpisane w konfiguracji, koniec wątku przepada, a odpowiedź wygląda
    poprawnie."""
    # Realny przypadek z 2026-08-02: wysłane 92 175 znaków, serwer naliczył 16 386 tokenów, bo
    # jego okno wynosiło 16384 zamiast skonfigurowanych 32768. Dwa pozostałe strażniki mierzą
    # wobec NUM_CTX z konfiguracji, więc oba to przepuściły — ten od konfiguracji nie zależy.
    client = OllamaLLMClient(
        model             = MODEL,
        env_prefix        = ENV_PREFIX,
        num_ctx           = 32768,
        max_output_tokens = 1500,
    )

    with pytest.raises(LLMError, match="przeczytał mniej"):
        client._to_completion(_answer(16386), elapsed_ms=6000, sent_chars=92175)


def test_the_message_points_at_the_window_setting():
    """Sprawdza, czy komunikat błędu o tym, że serwer przeczytał mniej, niż wysłaliśmy, wymienia
    zmienną `LLM_ANONYMIZATION_NUM_CTX`.

    Wyłapuje komunikat, który jej nie nazywa: przyczyną jest tu źle ustawione okno kontekstu,
    a nie treść zgłoszenia, więc bez tej wskazówki szukałoby się błędu w złym miejscu."""
    client = OllamaLLMClient(
        model             = MODEL,
        env_prefix        = ENV_PREFIX,
        num_ctx           = 32768,
        max_output_tokens = 1500,
    )

    with pytest.raises(LLMError) as exc:
        client._to_completion(_answer(16386), elapsed_ms=6000, sent_chars=92175)

    assert "LLM_ANONYMIZATION_NUM_CTX" in str(exc.value)


def test_intact_calls_are_not_flagged():
    """Sprawdza, czy trzy wywołania o zwykłym stosunku znaków do tokenów (około 1,3 znaku na token,
    na przykład 7168 znaków i 5400 tokenów) przechodzą bez błędu i oddają liczbę tokenów podaną
    przez serwer.

    Wyłapuje próg ustawiony za blisko zwykłych wartości: sprawdzenie ucięcia odrzucałoby wtedy
    poprawne odpowiedzi."""
    # Zmierzone na żywym podzie: 1,30 znaku na token przy dziewięciu nietkniętych wywołaniach.
    for sent_chars, prompt_tokens in [(7168, 5400), (8824, 6800), (5275, 4100)]:
        completion = make_client()._to_completion(
            _answer(prompt_tokens), elapsed_ms=5000, sent_chars=sent_chars
        )

        assert completion.prompt_tokens == prompt_tokens


def test_the_check_is_skipped_without_a_sent_length():
    """Sprawdza, czy odpowiedź przepisywana bez podanej długości wysłanego tekstu przechodzi bez
    błędu i oddaje 100 tokenów wejścia podane przez serwer.

    Wyłapuje sprawdzenie ucięcia, które wymaga tej długości albo jej brak traktuje jak ucięcie:
    przepisanie odpowiedzi bez tej informacji kończyłoby się wtedy błędem."""
    assert make_client()._to_completion(_answer(100), elapsed_ms=1.0).prompt_tokens == 100
