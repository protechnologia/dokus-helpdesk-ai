import time

# Three failure modes, kept apart because the caller's message names which one happened:
#   APITimeoutError    — the request outlived its timeout
#   APIConnectionError — could not establish a connection at all
#   APIStatusError     — provider answered, but with a non-2xx status
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
)

from app.llm.base import LLMClient, LLMCompletion
from app.llm.errors import LLMError
from app.llm.pricing_claude import calculate_cost_usd, price_of

# Ceiling on ONE answer, not a target. A parsed ticket is a small JSON object, but a thread with a
# quoted mail history can push the model into a long answer; cutting it off mid-JSON would waste
# the whole (already paid for) call, so the ceiling sits far above the expected size.
MAX_OUTPUT_TOKENS = 8_000

# Newer models REJECT the sampling parameters outright: sending `temperature` to Sonnet 5 returns
# `400 invalid_request_error: temperature is deprecated for this model`, while Haiku 4.5 still
# accepts it. Verified against the live API on 2026-08-01.
#
# The list holds the families that still take it, not the ones that refuse it, so a model released
# after this build defaults to NOT sending the parameter — a new model that quietly ignored an
# unsupported knob would be a worse outcome than one that never received it.
MODELS_ACCEPTING_TEMPERATURE = ("claude-haiku-4-5",)


class ClaudeLLMClient(LLMClient):
    """
    Description:
    Talks to the Claude API and is the ONLY module in this project allowed to import the Anthropic
    SDK (CLAUDE.md -> rule 4). Everything above it sees `LLMClient` and `LLMCompletion`, so
    swapping Claude for Bielik on RunPod is a configuration change, not a code change.

    Do czego:
    The Messages API is shaped differently from the OpenAI-compatible one this project will use
    for Bielik: the system prompt is a top-level argument rather than a message, answers arrive as
    a list of content blocks, and usage is reported over four token classes instead of two. Those
    differences are the reason this is a separate client rather than a branch inside a shared one
    (CLAUDE.md -> "Warstwa LLM").

    Flow:
        1. `get_llm_client()` builds it from `Settings`, failing fast when key or model is missing.
        2. `complete()` sends one prompt, with the system prompt passed as `system=`.
        3. The text blocks of the answer are joined, usage is read from `response.usage`, and the
           call is priced here — the price list is provider knowledge and stays on this side of
           the abstraction.
    """

    def __init__(
        self,
        api_key:     str,          # e.g. "sk-ant-api03-...KLUCZ"
        model:       str,          # e.g. "claude-haiku-4-5"
        timeout:     float = 60.0, # seconds
        temperature: float = 0.0,  # ignored by models that no longer accept the parameter
    ):
        """
        Description:
        Builds the async SDK client and validates that the model has a known price. Pricing is
        checked HERE, at construction, rather than after the first answer comes back: discovering
        an unpriced model at that point means the call was already paid for.

        Whether `temperature` is sent at all is settled here too, because newer models reject the
        parameter with a 400 instead of ignoring it — see `MODELS_ACCEPTING_TEMPERATURE`.

        Example args:
            api_key="sk-ant-api03-...KLUCZ"
            model="claude-haiku-4-5"
            timeout=60.0
            temperature=0.0

        Example result:
            ClaudeLLMClient ready to answer `complete()`, with its model's price row verified

        Raises:
            LLMConfigError: the model has no entry in the price table
        """
        # Fail now, while the exception can still name a configuration problem.
        price_of(model)

        self._model       = model
        self._temperature = temperature
        self._client      = AsyncAnthropic(api_key=api_key, timeout=timeout)

        # Decided once. A dated snapshot ("claude-haiku-4-5-20251001") must match its family, so
        # this is a prefix test rather than an exact membership check.
        self._accepts_temperature = model.startswith(MODELS_ACCEPTING_TEMPERATURE)

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
            LLMCompletion(text='{"problem": "…"}', model="claude-haiku-4-5", prompt_tokens=4820,
                          completion_tokens=640, latency_ms=3120.4, cost_usd=0.0080)

        Raises:
            LLMError: the provider timed out, was unreachable, refused the request, or answered
                with nothing usable
        """
        started_at = time.perf_counter()

        # --- build request ---
        # The system prompt is a TOP-LEVEL argument in this API, not a message with role="system".
        # Passing it as a message would make the model read it as user text and quietly weaken
        # every instruction it carries. Omitted entirely when absent — an explicit None is rejected.
        request: dict = {
            "model":      self._model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages":   [{"role": "user", "content": prompt}],
        }

        # Sent only where it is still accepted — elsewhere it is a hard 400, not a warning.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        if system is not None:
            request["system"] = system

        # --- call the provider ---
        try:
            response = await self._client.messages.create(**request)
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
        response,           # e.g. anthropic.types.Message with content=[TextBlock(text="{…}")]
        elapsed_ms: float,  # e.g. 3120.4
    ) -> LLMCompletion:
        """
        Description:
        Maps one SDK answer onto our own contract and prices it. Split out from `complete()`
        because it is pure: a test can feed it a stub response and assert the mapping without a
        network call and without an API key.

        Example args:
            response=Message(content=[TextBlock(text='{"problem": "…"}')], usage=Usage(…))
            elapsed_ms=3120.4

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="claude-haiku-4-5", cost_usd=0.0080, …)

        Raises:
            LLMError: the answer carried no text block (the model stopped before writing anything)
        """
        text  = self._extract_text(response)
        usage = response.usage

        # Cache counters are absent on SDK versions that do not report them, and `None` on a call
        # that used no caching; treat both as zero rather than letting `None` reach the arithmetic.
        cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens  = getattr(usage, "cache_read_input_tokens", 0) or 0

        # Priced against the model the response REPORTS, not the one we asked for. The two normally
        # match, but when they do not, the bill follows what actually ran.
        return LLMCompletion(
            text               = text,
            model              = response.model,
            prompt_tokens      = usage.input_tokens,
            completion_tokens  = usage.output_tokens,
            cache_write_tokens = cache_write_tokens,
            cache_read_tokens  = cache_read_tokens,
            latency_ms         = elapsed_ms,
            cost_usd           = calculate_cost_usd(
                model              = response.model,
                prompt_tokens      = usage.input_tokens,
                completion_tokens  = usage.output_tokens,
                cache_write_tokens = cache_write_tokens,
                cache_read_tokens  = cache_read_tokens,
            ),
        )

    @staticmethod
    def _extract_text(response) -> str:  # e.g. Message(content=[TextBlock(text='{"problem": …}')])
        """
        Description:
        Joins the text blocks of one answer. The answer is a LIST of blocks, not a string, and
        non-text blocks may appear among them — reading `content[0].text` blindly would raise on
        the first answer that opens with anything else.

        Example args:
            response=Message(content=[TextBlock(text='{"problem": "Brak tonera"}')])

        Example result:
            '{"problem": "Brak tonera"}'

        Raises:
            LLMError: no text block in the answer — nothing for the caller to parse
        """
        parts = [block.text for block in response.content if block.type == "text"]

        if not parts:
            raise LLMError(
                f"odpowiedź modelu nie zawiera tekstu (stop_reason={response.stop_reason})"
            )

        return "".join(parts)
