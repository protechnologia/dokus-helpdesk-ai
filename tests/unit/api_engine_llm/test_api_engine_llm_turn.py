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

# Kontrakt tury z narzędziami w `LLMClient`: kształt wyniku, klient bez tury, argumenty wywołania
# podane tekstem i to, co trafia do logu.

TICKET = "Nie przychodzą przesyłki z e-Doręczeń"

USER  = ChatMessage(role="user", content=TICKET)
TOOLS = [
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]


class CompletionOnlyClient(LLMClient):
    """Klient, który umie tylko `complete()` — tury z narzędziami nie implementuje."""

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


def test_a_client_without_tool_turns_cannot_be_built() -> None:
    """Sprawdza, czy klienta, który implementuje tylko `complete()`, nie da się w ogóle utworzyć:
    próba kończy się błędem wymieniającym brakującą metodę `complete_turn`.

    Wyłapuje nowego klienta dostawcy bez tury z narzędziami: pętla agenta trafiłaby na ten brak
    dopiero w środku żądania, zamiast przy budowie klienta."""
    with pytest.raises(TypeError, match="complete_turn"):
        CompletionOnlyClient()


def test_arguments_given_as_json_text_become_a_dictionary() -> None:
    """Sprawdza, czy argumenty wywołania narzędzia podane przez dostawcę jako tekst JSON stają się
    słownikiem z tymi samymi wartościami, z polskimi literami, a pusty tekst pustym słownikiem.

    Wyłapuje argumenty zgubione albo zniekształcone po drodze od dostawcy do narzędzia oraz błąd
    przy narzędziu bez argumentów, dla którego dostawca przysyła pusty tekst."""
    parsed = LLMClient._parse_arguments("find_tickets_vector", '{"problem": "Brak przesyłek"}')

    assert parsed == {"problem": "Brak przesyłek"}
    assert LLMClient._parse_arguments("list_docs", "")   == {}
    assert LLMClient._parse_arguments("list_docs", "{}") == {}


@pytest.mark.parametrize(
    "raw",
    ['{"problem": "Jan Kowalski', '["Jan Kowalski"]', '"Jan Kowalski"'],
    ids=["broken-json", "list", "text"],
)
def test_arguments_that_are_not_a_json_object_are_refused(raw: str) -> None:
    """Sprawdza, czy argumenty, które nie są obiektem JSON (urwany JSON, lista, sam tekst), kończą
    się wyjątkiem `LLMError`, który nazywa narzędzie, ale nie cytuje tego, co podał model.

    Wyłapuje turę przyjętą z argumentami, których nie da się zapisać w wywołaniu narzędzia, oraz
    komunikat błędu powtarzający treść argumentów, czyli dane ze zgłoszenia klienta."""
    with pytest.raises(LLMError) as exc:
        LLMClient._parse_arguments("find_tickets_vector", raw)

    assert "`find_tickets_vector`" in str(exc.value)
    assert "Kowalski"              not in str(exc.value)


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
