import time
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.llm.base import LLMClient, LLMCompletion
from app.llm.errors import LLMError

# Returned when nobody scripted an answer. A constant (not an echo of the prompt) so a test that
# accidentally asserts on it fails loudly instead of passing on coincidental input.
DEFAULT_FAKE_RESPONSE = "fake-llm-response"

FAKE_MODEL_NAME = "fake"


class LLMCall(BaseModel):
    """
    Description:
    One recorded invocation of `FakeLLMClient`. Lets a test assert WHAT was sent (did the prompt
    template really receive the ticket? was the system prompt attached?) without reaching into
    private attributes.
    """

    prompt: str         = Field(examples=["Zgłoszenie klienta:\n\nDrukarka nie drukuje…"])
    system: str | None  = Field(default=None, examples=["Jesteś parserem zgłoszeń helpdesku."])


class FakeLLMClient(LLMClient):
    """
    Description:
    The default implementation (`LLM_PROVIDER=fake`) and the one every unit test runs against.
    Sends nothing anywhere: `docker compose up` and `pytest` cost nothing and work offline
    (CLAUDE.md -> "Warstwa LLM"). It is also the seam for tests — scripted answers let a test
    drive the domain through a chosen model output.

    Flow:
        1. The test (or the factory) constructs it, optionally with `responses` — the answers to
           be returned, in order.
        2. Each `complete()` records the call in `calls` and returns the next scripted answer, or
           `DEFAULT_FAKE_RESPONSE` when nothing was scripted.
        3. Running out of scripted answers is an error, not a silent repeat: it means the code
           under test made more calls than the test expected.
    """

    def __init__(
        self,
        responses: Sequence[str] | None = None,  # e.g. ['{"problem": "Brak tonera"}']
    ):
        """
        Description:
        Prepares the scripted answers and the call log.

        Example args:
            responses=['{"problem": "Brak tonera"}', '{"problem": "Zacięcie papieru"}']

        Example result:
            FakeLLMClient returning those two answers in order, recording every call in `calls`
        """
        self._responses: list[str] = list(responses) if responses is not None else []
        self._next_index: int      = 0

        # Public on purpose: assertions read it, so it is part of this class's contract.
        self.calls: list[LLMCall] = []

    async def complete(
        self,
        prompt: str,                # e.g. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        system: str | None = None,  # e.g. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Records the call and answers from the script. No network, no sleep — the coroutine is
        async only to keep the same signature as a real provider.

        Example args:
            prompt="Zgłoszenie klienta:\\n\\nDrukarka nie drukuje…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text="fake-llm-response", model="fake", prompt_tokens=6, …)

        Raises:
            LLMError: the scripted answers ran out (more calls than the test set up)
        """
        started_at = time.perf_counter()

        self.calls.append(LLMCall(prompt=prompt, system=system))

        text       = self._next_response()
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        # A real provider bills the system prompt too, so the fake counts both parts as input.
        billed_input = prompt if system is None else f"{system}\n{prompt}"

        completion = LLMCompletion(
            text              = text,
            model             = FAKE_MODEL_NAME,
            prompt_tokens     = self._count_tokens(billed_input),
            completion_tokens = self._count_tokens(text),
            latency_ms        = elapsed_ms,
        )

        self._log_call(prompt, completion)

        return completion

    def _next_response(self) -> str:
        """
        Description:
        Takes the next scripted answer. Nothing scripted → the constant default; script exhausted
        → an error, because repeating the last answer would let an unexpected extra call pass
        unnoticed.

        Example args:
            (none)

        Example result:
            '{"problem": "Brak tonera"}'

        Raises:
            LLMError: every scripted answer has already been returned
        """
        if not self._responses:
            return DEFAULT_FAKE_RESPONSE

        if self._next_index >= len(self._responses):
            raise LLMError(
                f"FakeLLMClient ran out of scripted responses after {len(self._responses)} call(s)"
            )

        response = self._responses[self._next_index]
        self._next_index += 1

        return response

    @staticmethod
    def _count_tokens(text: str) -> int:   # e.g. "Drukarka nie drukuje"
        """
        Description:
        Approximates token count by counting whitespace-separated words. Good enough for a fake:
        the number only has to be deterministic and non-zero so the log shape gets exercised —
        a real tokenizer here would pull in a provider dependency for no gain.

        Example args:
            text="Drukarka nie drukuje"

        Example result:
            3
        """
        return len(text.split())
