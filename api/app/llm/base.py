import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMCompletion(BaseModel):
    """
    Description:
    One model answer together with the accounting the logs need. The domain reads `text` only;
    the remaining fields exist so every provider reports usage in the same shape and a cost
    report can be assembled later without touching call sites.
    """

    text:              str   = Field(examples=['{"problem": "Drukarka nie drukuje"}'])
    model:             str   = Field(examples=["bielik-11b-v3"])
    prompt_tokens:     int   = Field(examples=[482])
    completion_tokens: int   = Field(examples=[96])
    latency_ms:        float = Field(examples=[1240.5])

    # Cache accounting. Providers that bill cached input separately report it here; the rest leave
    # both at zero. Kept apart from `prompt_tokens` because the rates differ by an order of
    # magnitude (a cache read costs ~0.1x a fresh token, a write ~1.25x) — folding them into one
    # number would make the cost report wrong in whichever direction the caching went.
    cache_write_tokens: int = Field(default=0, examples=[1830])
    cache_read_tokens:  int = Field(default=0, examples=[1830])

    # Priced by the client that made the call, because the price list is provider knowledge and has
    # no business leaking into the domain (rule 4). Offline providers report 0.0 — a real zero, not
    # a missing value, so a run against the fake sums to "this cost nothing" rather than to None.
    cost_usd: float = Field(default=0.0, examples=[0.0123])


class LLMClient(ABC):
    """
    Description:
    The only way the rest of the application talks to a language model. Concrete subclasses wrap
    exactly one provider and are the ONLY place its SDK may be imported (CLAUDE.md -> rule 4),
    so swapping a cloud API for Bielik on RunPod is a configuration change, not a code change.

    Flow:
        1. `get_llm_client()` (see `factory.py`) builds the implementation named by `LLM_PROVIDER`
           and fails fast if its configuration is incomplete.
        2. The domain calls `complete()` with a prompt built from a template in `app/prompts/`.
        3. The implementation performs the call and returns `LLMCompletion`, reporting usage
           through `_log_call()` so every provider produces the same log line.

    Implementations are async with an explicit timeout: a hung model must not pin a request
    worker forever.
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,                # e.g. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        system: str | None = None,  # e.g. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Sends one prompt and returns the model answer. Single-shot by design — conversation
        state, if ever needed, belongs to the caller, not to the transport client.

        Example args:
            prompt="Zgłoszenie klienta:\\n\\nDrukarka nie drukuje…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="bielik-11b-v3", prompt_tokens=482, …)

        Raises:
            LLMError: the provider refused, timed out or returned an unusable answer
        """

    def _log_call(
        self,
        prompt:     str,             # e.g. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        completion: LLMCompletion,   # e.g. LLMCompletion(text="…", model="fake", …)
    ) -> None:
        """
        Description:
        Emits the accounting line for one call, in one shape for every provider. Prompt and
        answer go to DEBUG only — both carry customer data (CLAUDE.md -> "Logi i obserwowalność");
        INFO sees identifiers and numbers exclusively.

        Example args:
            prompt="Zgłoszenie klienta:…"
            completion=LLMCompletion(text="…", model="fake", prompt_tokens=12, …)

        Example result:
            None — one INFO record with usage, one DEBUG record with the texts
        """
        logger.info(
            "llm_call model=%s prompt_tokens=%d completion_tokens=%d "
            "cache_write_tokens=%d cache_read_tokens=%d latency_ms=%.1f cost_usd=%.6f",
            completion.model,
            completion.prompt_tokens,
            completion.completion_tokens,
            completion.cache_write_tokens,
            completion.cache_read_tokens,
            completion.latency_ms,
            completion.cost_usd,
        )
        logger.debug("llm_call prompt=%r response=%r", prompt, completion.text)
