import time

# Ollama speaks the OpenAI protocol, so the official SDK drives it — no second HTTP layer, and the
# three failure modes below keep the meanings they have there:
#   APITimeoutError    — the request outlived its timeout
#   APIConnectionError — could not establish a connection at all (Ollama not running)
#   APIStatusError     — the server answered, but with a non-2xx status
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.llm.base import LLMClient, LLMCompletion
from app.llm.errors import LLMConfigError, LLMError
from app.llm.pricing_selfhosted import calculate_cost_usd

# Fallbacks used when nothing is configured. Both are ENV settings (`LLM_NUM_CTX`,
# `LLM_MAX_OUTPUT_TOKENS`) because they depend on the model and the machine, not on this code.
#
# CRUCIAL: `num_ctx` here does NOT set the server's window — it only tells this client what the
# window IS, so it can refuse work that will not fit. Ollama ignores `num_ctx` sent in a request;
# measured 2026-08-02 against Ollama 0.32.5, where an ~18k-token prompt went through untouched with
# the request asking for a window of 1024. The window is set ONLY on the server, by the
# `OLLAMA_CONTEXT_LENGTH` environment variable (or `PARAMETER num_ctx` in a Modelfile, which beats
# everything). Setting this value higher than the server's real window means we submit prompts that
# get silently truncated — which is exactly what the checks below exist to catch.
#
# 8192 is what Bielik 4.5B v3.0 declares (`llama.context_length`, verified 2026-08-02). The answer
# budget is carved OUT of that window rather than added to it, so every token reserved for the
# answer is one the ticket cannot use — 1500 is generous for an artifact of a few hundred tokens.
DEFAULT_NUM_CTX           = 8_192
DEFAULT_MAX_OUTPUT_TOKENS = 1_500

# Ollama requires the Authorization header to exist but never checks it — the SDK refuses to build
# without a key, so this placeholder satisfies it. It is not a secret and must not be read from ENV:
# putting a real key here would ship it to a local process that has no use for it.
UNUSED_API_KEY = "ollama"

# Characters per token, used only to REFUSE work that cannot fit — never to trim it. Polish text
# tokenises at roughly 3 characters per token on Llama-family vocabularies; the estimate is
# deliberately pessimistic (a real ratio nearer 3.5–4 means we reject slightly early rather than
# submit a prompt that gets silently cut).
CHARS_PER_TOKEN = 3.0

# Ceiling on the same ratio, measured AFTER the answer comes back, to catch a truncation the
# configured window cannot reveal.
#
# Why a second, differently-shaped check: everything else here compares against `LLM_NUM_CTX`, a
# number a HUMAN typed. When that number is wrong — the server silently runs a smaller window than
# the model declares, e.g. because it lacked VRAM for the KV cache — both the length check and the
# window check pass while the tail of the thread is quietly dropped. This one needs no
# configuration at all: it compares what we SENT with what the server says it READ.
#
# Measured on the live pod 2026-08-02: 1.30 chars/token across nine intact calls, 5.63 on the one
# that was truncated. The threshold sits far above the intact figure, so ordinary variation between
# models and languages cannot trip it — only a server that read markedly less than it was given.
MAX_CHARS_PER_TOKEN_REPORTED = 3.0



class OllamaLLMClient(LLMClient):
    """
    Description:
    Talks to a model served locally by Ollama. Written as its own client rather than a subclass of
    `OpenAILLMClient` because what differs is not the request shape but everything AROUND it: the
    run is free, slow enough that timeouts are measured in minutes, needs no API key, and reports no
    cache counters. Sharing the code would mean a base class whose every setting has an exception.

    Do czego:
    This is the path Bielik takes (CLAUDE.md -> "Warstwa LLM"): the endpoint is OpenAI-compatible,
    so the vendor SDK still does the talking, but the pricing and the operational assumptions come
    from `pricing_selfhosted` — our own hardware bills no tokens.

    Flow:
        1. `get_llm_client()` builds it from `Settings`, requiring only `LLM_MODEL` and a base URL.
        2. `complete()` sends one prompt, prepending the system prompt as the first message.
        3. The answer text is read and usage is mapped; `cost_usd` is zero by construction, so the
           number worth reading is `latency_ms`.
    """

    def __init__(
        self,
        model:       str,                                   # e.g. "bielik-4.5b-v3.0-instruct:Q8_0"
        base_url:    str   = "http://localhost:11434/v1",   # Ollama's OpenAI-compatible endpoint
        timeout:     float = 1800.0,                        # seconds — 30 min, see below
        temperature: float = 0.0,                           # local models accept it without fuss
        num_ctx:     int   = DEFAULT_NUM_CTX,               # context window, stated explicitly
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS, # carved out of `num_ctx`
    ):
        """
        Description:
        Builds the async SDK client pointed at a local Ollama server. No price lookup guards this
        constructor — unlike the hosted clients, an unknown model here cannot produce a surprise
        bill, so refusing to start would block a run for no reason.

        The context window IS guarded, because getting it wrong is silent: Ollama defaults to 2048
        tokens whatever the model supports and drops the excess without a word, so a ticket parsed
        from half a thread would look like a correct artifact (CLAUDE.md -> rule 7).

        The default timeout is thirty minutes, not sixty seconds. A 4.5B model on CPU answers at
        roughly one token per second (measured 2026-08-02), so a full ticket takes minutes and the
        hosted default would abort every single call.

        Example args:
            model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
            base_url="http://localhost:11434/v1"
            timeout=1800.0
            temperature=0.0
            num_ctx=8192
            max_output_tokens=1500

        Example result:
            OllamaLLMClient ready to answer `complete()` against the local server

        Raises:
            LLMConfigError: the answer budget does not fit inside the context window
        """
        # Caught here rather than at the first call: a window smaller than its own answer budget
        # leaves negative room for the prompt, and every request would fail for a reason that reads
        # like a data problem instead of a configuration one.
        if max_output_tokens >= num_ctx:
            raise LLMConfigError(
                f"LLM_MAX_OUTPUT_TOKENS ({max_output_tokens}) musi być mniejsze niż "
                f"LLM_NUM_CTX ({num_ctx}) — odpowiedź dzieli okno kontekstu ze zgłoszeniem"
            )

        self._model             = model
        self._temperature       = temperature
        self._num_ctx           = num_ctx
        self._max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI(api_key=UNUSED_API_KEY, base_url=base_url, timeout=timeout)

        # Room left for the prompt once the answer has its share. Computed once, because it is the
        # number every call is checked against.
        self._max_prompt_chars = int((num_ctx - max_output_tokens) * CHARS_PER_TOKEN)

    async def complete(
        self,
        prompt: str,                # e.g. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] Nie działa…"
        system: str | None = None,  # e.g. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Sends one prompt and returns the answer together with its usage. Cost is always zero here;
        `latency_ms` is the field that carries information.

        Example args:
            prompt="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki\\n\\n[klient] Nie działa…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="bielik-4.5b-v3.0-instruct:Q8_0",
                          prompt_tokens=6200, completion_tokens=310, latency_ms=384000.0,
                          cost_usd=0.0)

        Raises:
            LLMError: the server timed out, was unreachable, refused the request, or answered with
                nothing usable
        """
        started_at = time.perf_counter()

        # --- refuse what cannot fit, before spending minutes on it ---
        self._reject_if_too_long(prompt, system)

        # --- build request ---
        messages: list[dict] = []

        if system is not None:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        # `max_completion_tokens` rather than the deprecated `max_tokens`: Ollama accepts both, and
        # this keeps one spelling across every OpenAI-protocol client in the project.
        # No `num_ctx` here on purpose: Ollama ignores it in a request (measured — see the module
        # comment). The window comes from the server's own `OLLAMA_CONTEXT_LENGTH`, so this client
        # can only VERIFY it, never impose it — which the two checks around this call do.
        request: dict = {
            "model":                 self._model,
            "max_completion_tokens": self._max_output_tokens,
            "messages":              messages,
            "temperature":           self._temperature,
        }

        # --- call the local server ---
        try:
            response = await self._client.chat.completions.create(**request)
        except APITimeoutError as exc:
            # On CPU this usually means the model is simply slower than the budget, not that
            # anything broke — the message says so, because the fix is a longer timeout.
            raise LLMError(
                f"model {self._model} nie odpowiedział w limicie czasu; "
                f"na CPU zwiększ LLM_TIMEOUT_SECONDS"
            ) from exc
        except APIConnectionError as exc:
            # The overwhelmingly likely cause of this one locally: the server is not running.
            raise LLMError(
                f"brak połączenia z serwerem Ollama pod {self._client.base_url}; "
                f"sprawdź, czy usługa działa"
            ) from exc
        except APIStatusError as exc:
            # Reached the server and was refused — most often an un-pulled model name.
            raise LLMError(
                f"serwer Ollama odrzucił żądanie dla modelu {self._model} "
                f"(HTTP {exc.status_code})"
            ) from exc

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        completion = self._to_completion(response, elapsed_ms, len(prompt) + len(system or ""))

        self._log_call(prompt, completion)

        return completion

    def _reject_if_too_long(
        self,
        prompt: str,         # e.g. "ZGŁOSZENIE 33319\nTemat: …" — a 87k-character thread
        system: str | None,  # e.g. the parsing prompt, ~5k characters
    ) -> None:
        """
        Description:
        Refuses a call whose input cannot fit the context window, instead of letting the server
        quietly drop the overflow.

        This is the one place that protects the artifact from a failure mode nothing downstream can
        detect: a thread cut in half still parses, still validates, and still produces a file that
        looks complete — while the resolution, which in this corpus tends to sit at the END of the
        thread, was never seen by the model. A loud refusal turns that into a decision the operator
        makes (shorter model? bigger window? skip the ticket?) rather than a silent data loss.

        The estimate is deliberately pessimistic, and it does NOT trim: trimming would recreate the
        exact problem it exists to prevent, only with our name on it.

        Example args:
            prompt="ZGŁOSZENIE 33319\\nTemat: …"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            None — returns quietly when the input fits

        Raises:
            LLMError: the input is longer than the window leaves room for
        """
        total_chars = len(prompt) + len(system or "")

        if total_chars <= self._max_prompt_chars:
            return

        raise LLMError(
            f"wejście za długie dla okna kontekstu: ~{total_chars:,} znaków przy limicie "
            f"~{self._max_prompt_chars:,} (LLM_NUM_CTX={self._num_ctx}, "
            f"LLM_MAX_OUTPUT_TOKENS={self._max_output_tokens}); "
            f"model ucina nadmiar po cichu, więc zgłoszenie zostaje pominięte"
        )

    def _reject_if_server_read_less(
        self,
        prompt_tokens: int,  # e.g. 16386 — what the server says it consumed
        sent_chars:    int,  # e.g. 92175 — what we actually sent
    ) -> None:
        """
        Description:
        Refuses an answer produced from less input than we sent, by comparing characters sent
        against tokens the server reports reading.

        The only check here that does NOT depend on `LLM_NUM_CTX`. That matters: when the configured
        window is larger than the one the server really runs — which happens when a runner quietly
        shrinks the window to fit available VRAM — the length check and the window check both pass
        while the tail of the thread is dropped. This one still fires, because the ratio between
        sent text and counted tokens cannot lie about it.

        Skipped when `sent_chars` is zero, so a caller mapping a stored response can reuse the
        mapping without inventing a length.

        Example args:
            prompt_tokens=16386
            sent_chars=92175

        Example result:
            None — returns quietly when the server read what it was given

        Raises:
            LLMError: the server counted far fewer tokens than the text could tokenise to
        """
        if not sent_chars or not prompt_tokens:
            return

        chars_per_token = sent_chars / prompt_tokens

        if chars_per_token <= MAX_CHARS_PER_TOKEN_REPORTED:
            return

        raise LLMError(
            f"serwer przeczytał mniej, niż wysłaliśmy: {sent_chars:,} znaków naliczone jako "
            f"{prompt_tokens:,} tokenów ({chars_per_token:.1f} znaku na token przy oczekiwanych "
            f"~1,3). Okno kontekstu serwera jest mniejsze niż LLM_NUM_CTX={self._num_ctx} — "
            f"zmierz je i popraw, zgłoszenie zostaje pominięte"
        )

    def _to_completion(
        self,
        response,           # e.g. ChatCompletion(choices=[Choice(message=…)], usage=Usage(…))
        elapsed_ms: float,  # e.g. 384000.0
        sent_chars: int = 0,  # e.g. 92175 — prompt + system, 0 skips the truncation ratio check
    ) -> LLMCompletion:
        """
        Description:
        Maps one answer onto our own contract. Split out from `complete()` because it is pure: a
        test can feed it a stub response and assert the mapping without a running Ollama server.

        Cache fields stay at their zero defaults — a local runner reports no cache counters, and a
        fabricated number there would be worse than an honest zero.

        Example args:
            response=ChatCompletion(choices=[…], usage=Usage(prompt_tokens=6200, …))
            elapsed_ms=384000.0

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="bielik-4.5b…", cost_usd=0.0, …)

        Raises:
            LLMError: the answer carried no text
        """
        text  = self._extract_text(response)
        usage = response.usage

        # Second line of defence, after the length check in `_reject_if_too_long`. That one works on
        # an ESTIMATE of the token count; this one reads what the server actually consumed. If the
        # prompt filled the whole window, the tail was almost certainly cut — and in this corpus the
        # tail is where the resolution lives.
        #
        # This check also catches the case the client cannot prevent: `LLM_NUM_CTX` configured
        # LARGER than the window the server actually runs with. The length check would then pass a
        # prompt the server truncates, and this is the only place that notices. Verified against the
        # live pod on 2026-08-02 by configuring 1024 against a server running 32768.
        if usage.prompt_tokens >= self._num_ctx:
            raise LLMError(
                f"prompt wypełnił całe okno kontekstu ({usage.prompt_tokens} z {self._num_ctx} "
                f"tokenów) — koniec wątku został najprawdopodobniej ucięty, artefakt odrzucony"
            )

        # Third check, and the only one that does not trust `LLM_NUM_CTX`. Compares what we SENT
        # with what the server says it READ: a server that quietly ran a smaller window reports far
        # fewer tokens than the text can possibly tokenise to.
        self._reject_if_server_read_less(usage.prompt_tokens, sent_chars)

        return LLMCompletion(
            text              = text,
            model             = response.model,
            prompt_tokens     = usage.prompt_tokens,
            completion_tokens = usage.completion_tokens,
            latency_ms        = elapsed_ms,
            cost_usd          = calculate_cost_usd(
                model             = response.model,
                prompt_tokens     = usage.prompt_tokens,
                completion_tokens = usage.completion_tokens,
            ),
        )

    @staticmethod
    def _extract_text(response) -> str:  # e.g. ChatCompletion(choices=[Choice(message=Message(…))])
        """
        Description:
        Reads the text of the first choice. `content` is None rather than empty when the model wrote
        nothing, so the empty case is reported as an error instead of returning a string nobody can
        parse — on a slow local run that distinction saves re-reading a whole log to find out why an
        artifact is missing.

        Example args:
            response=ChatCompletion(choices=[Choice(message=Message(content='{"problem": "…"}'))])

        Example result:
            '{"problem": "…"}'

        Raises:
            LLMError: no choices, or the answer carried no text
        """
        if not response.choices:
            raise LLMError("odpowiedź modelu nie zawiera żadnego wariantu odpowiedzi")

        choice = response.choices[0]
        text   = choice.message.content

        if not text:
            raise LLMError(
                f"odpowiedź modelu nie zawiera tekstu (finish_reason={choice.finish_reason})"
            )

        return text
