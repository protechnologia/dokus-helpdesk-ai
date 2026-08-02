import time

# Three failure modes, kept apart because the caller's message names which one happened:
#   APITimeoutError    — the request outlived its timeout
#   APIConnectionError — could not establish a connection at all
#   APIStatusError     — provider answered, but with a non-2xx status
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.llm.base import LLMClient, LLMCompletion
from app.llm.errors import LLMError
from app.llm.pricing_openai import calculate_cost_usd, price_of

# Ceiling on ONE answer, not a target. Set far above a parsed ticket's size because reasoning models
# spend part of this budget on tokens the caller never sees: exhausting it mid-JSON wastes the whole
# (already paid for) call. Sent as `max_completion_tokens` — see the flag below.
MAX_OUTPUT_TOKENS = 8_000

# Reasoning models REJECT `temperature` outright: o4-mini answers
# `400 Unsupported value: 'temperature' does not support 0 with this model` (verified on the live
# API 2026-08-02). Listing the families that REFUSE it — rather than those that accept it — is the
# safe direction here, because the refusing set is the small, known one: every GPT model in the
# price table takes the parameter, and a future GPT release almost certainly will too.
MODELS_REJECTING_TEMPERATURE = ("o1", "o3", "o4")


class OpenAILLMClient(LLMClient):
    """
    Description:
    Talks to the OpenAI Chat Completions API and is the ONLY module allowed to import the OpenAI SDK
    (CLAUDE.md -> rule 4). Everything above it sees `LLMClient` and `LLMCompletion`.

    Do czego:
    Written as a separate client rather than a branch inside `ClaudeLLMClient` because the two APIs
    differ in the SHAPE of the request, not the endpoint: the system prompt is a message with
    `role="system"` here (a top-level argument there), the answer is a single string (a list of
    content blocks there), and cached input arrives INSIDE the prompt count (a separate counter
    there). Verified against the live API on 2026-08-02.

    This client also serves the OpenAI-compatible endpoints this project targets later (Bielik on
    RunPod, Ollama, vLLM) through `base_url` — that is why the URL is a constructor argument rather
    than a hardcoded host.

    Flow:
        1. `get_llm_client()` builds it from `Settings`, failing fast when key or model is missing.
        2. `complete()` sends one prompt, prepending the system prompt as the first message.
        3. The answer text is read, usage is mapped onto our four token classes, and the call is
           priced here — the price list is provider knowledge and stays on this side.
    """

    def __init__(
        self,
        api_key:     str,                 # e.g. "sk-proj-...KLUCZ"
        model:       str,                 # e.g. "gpt-5.4-mini"
        base_url:    str | None = None,   # e.g. "https://api.runpod.ai/v2/xyz/openai/v1"
        timeout:     float      = 60.0,   # seconds
        temperature: float      = 0.0,    # ignored by models that reject the parameter
    ):
        """
        Description:
        Builds the async SDK client and validates that the model has a known price. Pricing is
        checked HERE, at construction, rather than after the first answer: discovering an unpriced
        model at that point means the call was already paid for.

        Whether `temperature` is sent at all is settled here too, because reasoning models reject it
        with a 400 instead of ignoring it — see `MODELS_REJECTING_TEMPERATURE`.

        Example args:
            api_key="sk-proj-...KLUCZ"
            model="gpt-5.4-mini"
            base_url=None
            timeout=60.0
            temperature=0.0

        Example result:
            OpenAILLMClient ready to answer `complete()`, with its model's price row verified

        Raises:
            LLMConfigError: the model has no entry in the price table
        """
        # Fail now, while the exception can still name a configuration problem.
        price_of(model)

        self._model       = model
        self._temperature = temperature

        # `base_url=None` lets the SDK use its own default; passing an empty string would send the
        # request to a broken URL instead (CLAUDE.md -> "Pułapki": pusty string zamiast braku).
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout)

        # Decided once. A dated snapshot ("o4-mini-2025-04-16") must match its family, so this is a
        # prefix test rather than an exact membership check.
        self._accepts_temperature = not model.startswith(MODELS_REJECTING_TEMPERATURE)

    async def complete(
        self,
        prompt: str,                # e.g. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] Nie działa…"
        system: str | None = None,  # e.g. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Sends one prompt and returns the answer together with its usage and cost.

        Example args:
            prompt="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki\\n\\n[klient] Nie działa…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="gpt-5.4-mini", prompt_tokens=4820,
                          completion_tokens=640, latency_ms=3120.4, cost_usd=0.0064)

        Raises:
            LLMError: the provider timed out, was unreachable, refused the request, or answered
                with nothing usable
        """
        started_at = time.perf_counter()

        # --- build request ---
        # The system prompt is a MESSAGE here, not a top-level argument as in the Messages API.
        messages: list[dict] = []

        if system is not None:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        # `max_completion_tokens`, never `max_tokens`: the newer models reject the older name with a
        # hard 400, and the new name works on every model in the price table (verified 2026-08-02).
        request: dict = {
            "model":                 self._model,
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
            "messages":              messages,
        }

        # Sent only where it is accepted — on reasoning models it is a hard 400, not a warning.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        # --- call the provider ---
        try:
            response = await self._client.chat.completions.create(**request)
        except APITimeoutError as exc:
            # Ran past the deadline: the request may or may not have been processed on their side.
            raise LLMError(f"przekroczono limit czasu wywołania modelu {self._model}") from exc
        except APIConnectionError as exc:
            # Never reached the provider at all — network, DNS or a wrong base URL.
            raise LLMError(f"brak połączenia z API modelu {self._model}") from exc
        except APIStatusError as exc:
            # Reached them and was refused: bad key, unknown model, rate limit, provider outage.
            # Only the status code goes into our message; the body may quote the prompt back, and
            # the prompt carries customer data (CLAUDE.md -> "Logi i obserwowalność").
            raise LLMError(
                f"API modelu {self._model} odrzuciło żądanie (HTTP {exc.status_code})"
            ) from exc

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        completion = self._to_completion(response, elapsed_ms)

        self._log_call(prompt, completion)

        return completion

    def _to_completion(
        self,
        response,           # e.g. ChatCompletion(choices=[Choice(message=…)], usage=Usage(…))
        elapsed_ms: float,  # e.g. 3120.4
    ) -> LLMCompletion:
        """
        Description:
        Maps one SDK answer onto our own contract and prices it. Split out from `complete()` because
        it is pure: a test can feed it a stub response and assert the mapping without a network call
        and without an API key.

        Example args:
            response=ChatCompletion(choices=[…], usage=CompletionUsage(prompt_tokens=4820, …))
            elapsed_ms=3120.4

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="gpt-5.4-mini", cost_usd=0.0064, …)

        Raises:
            LLMError: the answer carried no text (the model stopped before writing anything)
        """
        text  = self._extract_text(response)
        usage = response.usage

        # Cached input is reported nested, and the whole branch is absent on a call that used no
        # caching; treat every missing level as zero rather than let `None` reach the arithmetic.
        details           = getattr(usage, "prompt_tokens_details", None)
        cache_read_tokens = getattr(details, "cached_tokens", 0) or 0

        # Priced against the model the response REPORTS, not the one we asked for. The two normally
        # match, but when they do not, the bill follows what actually ran.
        return LLMCompletion(
            text              = text,
            model             = response.model,
            prompt_tokens     = usage.prompt_tokens,
            completion_tokens = usage.completion_tokens,
            # No cache-WRITE class on this provider: caching is automatic and only reads are
            # discounted, so the field stays at its zero default rather than carrying a fake number.
            cache_read_tokens = cache_read_tokens,
            latency_ms        = elapsed_ms,
            cost_usd          = calculate_cost_usd(
                model             = response.model,
                prompt_tokens     = usage.prompt_tokens,
                completion_tokens = usage.completion_tokens,
                cache_read_tokens = cache_read_tokens,
            ),
        )

    @staticmethod
    def _extract_text(response) -> str:  # e.g. ChatCompletion(choices=[Choice(message=Message(…))])
        """
        Description:
        Reads the text of the first choice. `content` is None rather than empty when the model wrote
        nothing — a refusal, or a reasoning model that spent its whole budget on thinking — so the
        empty case is reported as an error instead of returning a string nobody can parse.

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
