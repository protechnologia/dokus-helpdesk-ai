import logging

import pytest
from pydantic import ValidationError

from app.engine_llm import (
    ChatMessage,
    FakeLLMClient,
    LLMClient,
    LLMCompletion,
    LLMError,
    LLMTurn,
    LLMUsage,
    ToolDefinition,
)

# Kontrakt tury z narzędziami w `LLMClient`: kształt wyniku, klient, który tury jeszcze nie umie,
# i to, co trafia do logu.

TICKET = "Nie przychodzą przesyłki z e-Doręczeń"

USER  = ChatMessage(role="user", content=TICKET)
TOOLS = [
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]


class CompletionOnlyClient(LLMClient):
    """Klient, który umie tylko `complete()` — jak klienci dostawców przed p. 17."""

    async def complete(
        self,
        prompt: str,                # np. "Zgłoszenie klienta…"
        system: str | None = None,  # np. "Jesteś parserem zgłoszeń."
    ) -> LLMCompletion:
        """
        Description:
        Oddaje stałą odpowiedź; ten test jej nie woła.

        Example args:
            prompt="Zgłoszenie klienta…"
            system=None

        Example result:
            LLMCompletion(text="ok", model="test", prompt_tokens=1, completion_tokens=1, …)
        """
        return LLMCompletion(
            text="ok", model="test", prompt_tokens=1, completion_tokens=1, latency_ms=0.0
        )


def test_a_turn_must_be_a_model_message() -> None:
    """Sprawdza, czy wynik tury modelu (`LLMTurn`) odrzuca wiadomość o roli `user` wyjątkiem
    `ValidationError`.

    Wyłapuje klienta, który jako turę modelu oddałby wiadomość innej roli: doklejona do rozmowy
    zepsułaby ją po cichu, a dostawca odrzuciłby dopiero następne żądanie."""
    with pytest.raises(ValidationError):
        LLMTurn(message=USER, model="fake", latency_ms=0.0, usage=LLMUsage(calls=1))


async def test_a_client_without_tool_turns_says_so() -> None:
    """Sprawdza, czy klient, który umie tylko `complete()`, na wywołanie tury z narzędziami
    odpowiada wyjątkiem `LLMError` z nazwą swojej klasy.

    Wyłapuje domyślne `complete_turn()`, które zamiast błędu oddaje po cichu odpowiedź bez narzędzi:
    dziś turę z narzędziami umie tylko atrapa, więc u prawdziwego dostawcy pętla agenta szłaby dalej
    na odpowiedzi, której model nie udzielił."""
    with pytest.raises(LLMError, match="CompletionOnlyClient"):
        await CompletionOnlyClient().complete_turn("Jesteś asystentem.", [USER], TOOLS)


async def test_the_turn_is_logged_without_the_conversation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sprawdza, czy tura modelu zostawia na poziomie INFO jeden wpis `llm_call` z modelem
    i liczbami, bez treści zgłoszenia, a treść rozmowy trafia tylko na poziom DEBUG.

    Wyłapuje wpis INFO, do którego trafia treść rozmowy: zgłoszenie to dane klienta i nie może
    znaleźć się w zwykłych logach."""
    caplog.set_level(logging.DEBUG, logger="app.engine_llm.base")

    await FakeLLMClient().complete_turn("Jesteś asystentem.", [USER], TOOLS)

    info  = [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]
    debug = [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG]

    assert len(info) == 1
    assert info[0].startswith("llm_call model=fake")
    assert TICKET not in info[0]
    assert TICKET     in debug[0]
