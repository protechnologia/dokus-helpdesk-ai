import asyncio

import pytest
from pydantic import BaseModel

from app.config import LLMSettings
from app.engine_llm import ChatMessage, LLMTurn, ToolDefinition, get_llm_client
from tests.conftest import live_generation_llm

pytestmark = pytest.mark.llm_live

# Tura z narzędziami na prawdziwym modelu generującym z konfiguracji (`LLM_GENERATION_*`):
# `Settings` -> `get_llm_client()` -> `complete_turn()`. Testy sprawdzają to, czego żadna atrapa
# nie pokaże: czy dostawca przyjmuje narzędzia i rozmowę w kształcie, w jakim wysyła je nasz
# klient, czy z jego odpowiedzi da się odczytać wywołanie narzędzia i czy druga tura — z wynikiem
# narzędzia i z tym, co dostawca każe odesłać bez zmian — też jest przyjmowana.
#
# KOSZTUJE: jeden przebieg pliku to dwie krótkie tury modelu, policzone raz i wspólne dla
# wszystkich testów. Narzędzia są tu zmyślone i niczego nie wykonują; pętlę z narzędziami
# produktu sprawdza test grafu `search` (`tests/integration/api_agent_graphs/`).

# Dostawca self-hosted: nasz sprzęt nie nalicza tokenów, więc koszt tury to zero.
PROVIDER_SELFHOSTED = "ollama"

NOTE_ID  = "n-17"
PASSWORD = "żółw"

SYSTEM_PROMPT = (
    f"Masz dwa narzędzia. Najpierw odczytaj notatkę o identyfikatorze {NOTE_ID} narzędziem "
    f"`read_note`. Gdy dostaniesz jej treść, zakończ narzędziem `respond`, podając w polu "
    f"`answer` hasło z notatki."
)
USER_PROMPT = "Podaj hasło z notatki."

TOOLS = [
    ToolDefinition(
        name        = "read_note",
        description = "Czyta notatkę o podanym identyfikatorze i oddaje jej treść.",
        parameters  = {
            "type":                 "object",
            "properties":           {"note_id": {"type": "string"}},
            "required":             ["note_id"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name        = "respond",
        description = "Kończy rozmowę: podaje odpowiedź dla użytkownika.",
        parameters  = {
            "type":                 "object",
            "properties":           {"answer": {"type": "string"}},
            "required":             ["answer"],
            "additionalProperties": False,
        },
    ),
]

# Wynik zmyślonego narzędzia. Hasło stoi WYŁĄCZNIE tutaj: model, który podaje je w drugiej turze,
# musiał przeczytać wynik narzędzia.
NOTE_RESULT = f'{{"note_id": "{NOTE_ID}", "text": "Hasło do skrzynki: {PASSWORD}"}}'


class LiveTurns(BaseModel):
    """Dwie tury prawdziwego modelu zebrane raz na plik, z nazwą dostawcy z konfiguracji."""

    provider: str
    first:    LLMTurn
    second:   LLMTurn


async def _run_two_turns(
    llm: LLMSettings,  # np. Settings().llm_generation()
) -> LiveTurns:
    """
    Description:
    Buduje klienta modelu z podanej konfiguracji i prowadzi z nim dwie tury: w pierwszej model ma
    wywołać narzędzie, a druga dostaje całą rozmowę razem z wynikiem tego narzędzia. To jedyne
    miejsce w pliku, które woła model.

    Na każde wywołanie z pierwszej tury odpowiada tym samym wynikiem notatki, żeby rozmowa była
    poprawna także wtedy, gdy model wywoła coś innego, niż powinien — ocenią to testy.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)

    Example result:
        LiveTurns(provider="openai",
                  first=LLMTurn(message=ChatMessage(tool_calls=[ToolCall(name="read_note", …)]), …),
                  second=LLMTurn(message=ChatMessage(tool_calls=[ToolCall(name="respond", …)]), …))

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział w czasie albo oddał turę nie do użycia
    """
    client = get_llm_client(llm)
    user   = ChatMessage(role="user", content=USER_PROMPT)

    # --- pierwsza tura: model ma sięgnąć po notatkę ---
    first = await client.complete_turn(SYSTEM_PROMPT, [user], TOOLS)

    # --- wyniki narzędzi: po jednym na każde wywołanie, z jego identyfikatorem ---
    results = [
        ChatMessage(role="tool", call_id=call.call_id, content=NOTE_RESULT)
        for call in first.message.tool_calls
    ]

    # --- druga tura: cała rozmowa, z turą modelu taką, jaką oddał klient ---
    second = await client.complete_turn(SYSTEM_PROMPT, [user, first.message, *results], TOOLS)

    turns = LiveTurns(
        provider = llm.provider.strip().lower(),
        first    = first,
        second   = second,
    )

    return turns


@pytest.fixture(scope="module")
def turns(
    request: pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
) -> LiveTurns:
    """
    Description:
    Dwie tury prawdziwego modelu, policzone raz na plik (`_run_two_turns()`), żeby każdy test nie
    płacił za własne wywołania. Konfigurację bierze przez `live_generation_llm()`, które odmawia,
    gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        LiveTurns(provider="openai", first=LLMTurn(…), second=LLMTurn(…))
    """
    return asyncio.run(_run_two_turns(live_generation_llm(request.config)))


def test_the_first_turn_calls_the_tool_with_its_arguments(turns: LiveTurns) -> None:
    """Sprawdza, czy model w pierwszej turze wywołuje narzędzie `read_note`, jedno, z argumentem
    `note_id` równym „n-17", tak jak kazał prompt systemowy.

    Wyłapuje definicje narzędzi wysłane w kształcie, którego dostawca nie rozumie, oraz
    odpowiedź, z której klient nie umie odczytać nazwy narzędzia albo jego argumentów."""
    calls = turns.first.message.tool_calls

    assert [call.name for call in calls] == ["read_note"]
    assert calls[0].arguments            == {"note_id": NOTE_ID}


def test_the_model_reads_the_tool_result_in_the_second_turn(turns: LiveTurns) -> None:
    """Sprawdza, czy druga tura, wysłana z całą rozmową i wynikiem narzędzia, kończy się
    wywołaniem `respond` z hasłem „żółw", które stało wyłącznie w wyniku narzędzia.

    Wyłapuje rozmowę, której dostawca nie przyjmuje w drugiej turze (wynik narzędzia bez
    powiązania z wywołaniem, zgubione elementy rozumowania do odesłania), oraz wynik narzędzia,
    który do modelu nie dociera."""
    calls = turns.second.message.tool_calls

    assert [call.name for call in calls] == ["respond"]
    assert PASSWORD in calls[0].arguments["answer"].lower()


def test_the_usage_of_each_turn_is_counted_and_priced(turns: LiveTurns) -> None:
    """Sprawdza, czy każda z dwóch tur ma policzone zużycie: jedno wywołanie modelu, wejście
    w którejś z trzech klas tokenów, co najmniej jeden token wyjścia i koszt większy od zera,
    a przy modelu self-hosted równy zeru.

    Wyłapuje turę, której liczniki klient czyta z niewłaściwych pól i zgłasza zera: koszt sprawy
    w odpowiedzi API byłby wtedy zaniżony o wszystkie tury z narzędziami, bez żadnego błędu."""
    for turn in (turns.first, turns.second):
        usage        = turn.usage
        input_tokens = usage.prompt_tokens + usage.cache_write_tokens + usage.cache_read_tokens

        assert usage.calls             == 1
        assert input_tokens            > 0
        assert usage.completion_tokens > 0

        if turns.provider == PROVIDER_SELFHOSTED:
            assert usage.cost_usd == 0.0
        else:
            assert usage.cost_usd > 0
