from pathlib import Path

import pytest

from app.llm import LLMConfigError, LLMError, client_ollama
from app.llm.client_ollama import OllamaLLMClient

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
    return OllamaLLMClient(model=MODEL)


def test_maps_usage_and_text():
    """Odpowiedź z tekstem → tekst, model i tokeny przepisane do LLMCompletion."""
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
    """Przebieg lokalny → koszt zero; płacimy prądem, nie tokenami."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=6200, completion_tokens=310),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cost_usd == 0.0


def test_any_model_name_is_accepted():
    """Dowolny tag modelu → klient powstaje; lokalny model nie ma cennika do sprawdzenia."""
    # Odwrotnie niż w klientach chmurowych, gdzie nieznany model to LLMConfigError: tu nie ma
    # rachunku, który mógłby zaskoczyć.
    assert OllamaLLMClient(model="jakis/nowy-model:latest")


def test_cache_fields_stay_at_zero():
    """Brak liczników cache → zera, nie zmyślona liczba."""
    response = StubResponse(
        choices = [StubChoice("ok")],
        usage   = StubUsage(prompt_tokens=100, completion_tokens=50),
    )

    completion = make_client()._to_completion(response, elapsed_ms=1.0)

    assert completion.cache_read_tokens  == 0
    assert completion.cache_write_tokens == 0


def test_answer_without_text_raises():
    """Odpowiedź z pustą treścią → LLMError z powodem zakończenia, nie pusty string."""
    response = StubResponse(
        choices = [StubChoice(None, finish_reason="length")],
        usage   = StubUsage(prompt_tokens=10, completion_tokens=4000),
    )

    with pytest.raises(LLMError) as exc:
        make_client()._to_completion(response, elapsed_ms=1.0)

    assert "length" in str(exc.value)


def test_answer_without_choices_raises():
    """Odpowiedź bez wariantów → LLMError, nie IndexError z wnętrza klienta."""
    response = StubResponse(choices=[], usage=StubUsage(prompt_tokens=10, completion_tokens=0))

    with pytest.raises(LLMError):
        make_client()._to_completion(response, elapsed_ms=1.0)


def test_default_timeout_fits_a_cpu_run():
    """Domyślny timeout liczony w minutach — na CPU jedno zgłoszenie trwa dłużej niż minutę."""
    # Zmierzone 2026-08-02: ~1 token/s na 4.5B bez GPU, więc domyślne 60 s z klientów chmurowych
    # przerwałoby każde wywołanie.
    assert make_client()._client.timeout >= 600


def test_points_at_the_local_server_by_default():
    """Bez podanego adresu → localhost:11434; port jest ustalony przez narzędzie."""
    assert "11434" in str(make_client()._client.base_url)


def test_context_window_is_stated_explicitly():
    """Klient trzyma jawne okno kontekstu — Ollama domyślnie tnie do 2048 bez ostrzeżenia."""
    assert make_client()._num_ctx == 8192


def test_input_longer_than_the_window_is_refused():
    """Wejście dłuższe niż okno → LLMError przed wysłaniem, nie ciche ucięcie wątku."""
    # Zgłoszenie 33319 ma 87 tys. znaków; przy oknie 8192 tokenów nie ma szans się zmieścić.
    with pytest.raises(LLMError, match="za długie"):
        make_client()._reject_if_too_long("x" * 87_000, system=None)


def test_the_refusal_names_the_settings_to_change():
    """Komunikat odmowy wskazuje zmienne konfiguracji — operator wie, co podnieść."""
    with pytest.raises(LLMError) as exc:
        make_client()._reject_if_too_long("x" * 87_000, system=None)

    assert "LLM_NUM_CTX"           in str(exc.value)
    assert "LLM_MAX_OUTPUT_TOKENS" in str(exc.value)


def test_system_prompt_counts_towards_the_limit():
    """Prompt systemowy liczy się do limitu — dzieli okno ze zgłoszeniem, nie stoi obok niego."""
    client = make_client()
    tuz_pod_limitem = "x" * (client._max_prompt_chars - 10)

    client._reject_if_too_long(tuz_pod_limitem, system=None)          # samo zgłoszenie: mieści się

    with pytest.raises(LLMError):                                      # z promptem: już nie
        client._reject_if_too_long(tuz_pod_limitem, system="y" * 100)


def test_input_that_fits_passes_quietly():
    """Wejście mieszczące się w oknie → brak wyjątku; strażnik nie może blokować normalnej pracy."""
    assert make_client()._reject_if_too_long("krótkie zgłoszenie", system="prompt") is None


def test_answer_filling_the_whole_window_is_rejected():
    """Prompt zajął całe okno → LLMError; koniec wątku (z rozwiązaniem) został ucięty."""
    # Druga linia obrony: sprawdzenie długości działa na SZACUNKU, to na faktycznym zużyciu.
    response = StubResponse(
        choices = [StubChoice('{"problem": "…"}')],
        usage   = StubUsage(prompt_tokens=8192, completion_tokens=100),
    )

    with pytest.raises(LLMError, match="ucięty"):
        make_client()._to_completion(response, elapsed_ms=1.0)


def test_answer_budget_larger_than_the_window_fails_at_build_time():
    """Budżet odpowiedzi ≥ okno → LLMConfigError; inaczej na prompt zostaje ujemne miejsce."""
    with pytest.raises(LLMConfigError, match="LLM_MAX_OUTPUT_TOKENS"):
        OllamaLLMClient(model=MODEL, num_ctx=1000, max_output_tokens=1000)


def test_answer_budget_is_carved_out_of_the_window():
    """Limit na prompt = okno minus odpowiedź — budżet dzieli okno, nie dokłada się do niego."""
    client = OllamaLLMClient(model=MODEL, num_ctx=8192, max_output_tokens=1500)

    assert client._max_prompt_chars < 8192 * 3


def test_num_ctx_is_not_sent_in_the_request():
    """Klient NIE wysyła num_ctx w żądaniu — Ollama go ignoruje, więc byłby martwym kodem."""
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
    """Serwer naliczył za mało tokenów → LLMError, mimo że okno w configu jest źle ustawione."""
    # Realny przypadek z 2026-08-02: wysłane 92 175 znaków, serwer naliczył 16 386 tokenów, bo
    # jego okno wynosiło 16384 zamiast skonfigurowanych 32768. Dwa pozostałe strażniki mierzą
    # wobec LLM_NUM_CTX, więc oba to przepuściły — ten nie zależy od konfiguracji.
    client = OllamaLLMClient(model=MODEL, num_ctx=32768, max_output_tokens=1500)

    with pytest.raises(LLMError, match="przeczytał mniej"):
        client._to_completion(_answer(16386), elapsed_ms=6000, sent_chars=92175)


def test_the_message_points_at_the_window_setting():
    """Komunikat wskazuje LLM_NUM_CTX — to je trzeba zmierzyć i poprawić, nie treść zgłoszenia."""
    client = OllamaLLMClient(model=MODEL, num_ctx=32768, max_output_tokens=1500)

    with pytest.raises(LLMError) as exc:
        client._to_completion(_answer(16386), elapsed_ms=6000, sent_chars=92175)

    assert "LLM_NUM_CTX" in str(exc.value)


def test_intact_calls_are_not_flagged():
    """Poprawne wywołania → brak alarmu; próg leży daleko od zmierzonego stosunku."""
    # Zmierzone na żywym podzie: 1,30 znaku na token przy dziewięciu nietkniętych wywołaniach.
    for sent_chars, prompt_tokens in [(7168, 5400), (8824, 6800), (5275, 4100)]:
        completion = make_client()._to_completion(
            _answer(prompt_tokens), elapsed_ms=5000, sent_chars=sent_chars
        )

        assert completion.prompt_tokens == prompt_tokens


def test_the_check_is_skipped_without_a_sent_length():
    """Brak informacji o długości wejścia → sprawdzenie pomijane, nie fałszywy alarm."""
    assert make_client()._to_completion(_answer(100), elapsed_ms=1.0).prompt_tokens == 100
