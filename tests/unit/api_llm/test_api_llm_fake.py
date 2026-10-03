import pytest

from app.llm import FakeLLMClient, LLMError
from app.llm.client_fake import DEFAULT_FAKE_RESPONSE, FAKE_MODEL_NAME


async def test_unscripted_call_returns_the_default_answer() -> None:
    """No responses given → the documented constant, so a bare fake is usable without setup."""
    client = FakeLLMClient()

    completion = await client.complete("Drukarka nie drukuje")

    assert completion.text == DEFAULT_FAKE_RESPONSE


async def test_scripted_answers_are_returned_in_order() -> None:
    """Two scripted answers → returned first-to-last, so a test can drive a multi-step flow."""
    client = FakeLLMClient(responses=['{"problem": "Brak tonera"}', '{"problem": "Zacięcie"}'])

    first  = await client.complete("zgłoszenie 1")
    second = await client.complete("zgłoszenie 2")

    assert (first.text, second.text) == ('{"problem": "Brak tonera"}', '{"problem": "Zacięcie"}')


async def test_every_call_is_recorded_with_its_prompts() -> None:
    """Prompt and system prompt → readable from `calls`, which is how tests assert on input."""
    client = FakeLLMClient()

    await client.complete("Drukarka nie drukuje", system="Jesteś parserem zgłoszeń.")

    assert len(client.calls) == 1
    assert client.calls[0].prompt == "Drukarka nie drukuje"
    assert client.calls[0].system == "Jesteś parserem zgłoszeń."


async def test_running_out_of_scripted_answers_fails_loudly() -> None:
    """One answer scripted, two calls made → LLMError, never a silent repeat of the last answer."""
    client = FakeLLMClient(responses=["jedyna odpowiedź"])

    await client.complete("zgłoszenie 1")

    with pytest.raises(LLMError):
        await client.complete("zgłoszenie 2")


async def test_completion_reports_usage_for_the_log_line() -> None:
    """System + prompt in, answer out → model name and both token counts filled in."""
    client = FakeLLMClient(responses=["dwa slowa"])

    completion = await client.complete("trzy slowa razem", system="jeden")

    assert completion.model             == FAKE_MODEL_NAME
    assert completion.prompt_tokens     == 4   # "jeden" + three words of the prompt
    assert completion.completion_tokens == 2
    assert completion.latency_ms        >= 0
