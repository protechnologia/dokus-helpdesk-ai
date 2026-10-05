import pytest

from app.engine_llm import ChatMessage, FakeLLMClient, LLMError, ToolCall, ToolDefinition
from app.engine_llm.client.fake import DEFAULT_FAKE_RESPONSE, FAKE_MODEL_NAME

# Atrapa modelu: scenariusz odpowiedzi dla `complete()` i scenariusz tur dla `complete_turn()`.

SYSTEM = "Jesteś asystentem wdrożeniowca helpdesku."

USER   = ChatMessage(role="user", content="Nie przychodzą przesyłki z e-Doręczeń")
SEARCH = ChatMessage(
    role       = "assistant",
    tool_calls = [ToolCall(call_id="call_1", name="find_docs_text", arguments={"words": "limit"})],
)
ANSWER = ChatMessage(
    role       = "assistant",
    tool_calls = [ToolCall(call_id="call_2", name="respond_search", arguments={})],
)

TOOLS = [
    ToolDefinition(name="find_docs_text", description="Szuka.", parameters={"type": "object"}),
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]


async def test_unscripted_call_returns_the_default_answer() -> None:
    """Sprawdza, czy atrapa modelu utworzona bez scenariusza odpowiada na `complete()` stałym,
    udokumentowanym tekstem (`DEFAULT_FAKE_RESPONSE`).

    Wyłapuje atrapę, która bez przygotowań zgłasza błąd albo odpowiada czymś innym: przestałaby
    wtedy działać konfiguracja domyślna i każdy test, który scenariusza nie podaje."""
    client = FakeLLMClient()

    completion = await client.complete("Drukarka nie drukuje")

    assert completion.text == DEFAULT_FAKE_RESPONSE


async def test_scripted_answers_are_returned_in_order() -> None:
    """Sprawdza, czy dwie zaplanowane odpowiedzi wracają w kolejności, w jakiej je podano: pierwsze
    wywołanie dostaje pierwszą, drugie drugą.

    Wyłapuje atrapę, która myli kolejność albo powtarza pierwszą odpowiedź: test nie mógłby wtedy
    przeprowadzić kodu przez kilka wywołań modelu z różnymi wynikami."""
    client = FakeLLMClient(responses=['{"problem": "Brak tonera"}', '{"problem": "Zacięcie"}'])

    first  = await client.complete("zgłoszenie 1")
    second = await client.complete("zgłoszenie 2")

    assert (first.text, second.text) == ('{"problem": "Brak tonera"}', '{"problem": "Zacięcie"}')


async def test_every_call_is_recorded_with_its_prompts() -> None:
    """Sprawdza, czy po jednym wywołaniu `complete()` atrapa ma w `calls` jeden wpis z promptem
    i promptem systemowym, które dostała.

    Wyłapuje atrapę, która nie zapisuje wywołań albo gubi prompt systemowy: inne testy czytają ten
    dziennik, żeby sprawdzić, co poszło do modelu, i straciłyby tę możliwość."""
    client = FakeLLMClient()

    await client.complete("Drukarka nie drukuje", system="Jesteś parserem zgłoszeń.")

    assert len(client.calls) == 1
    assert client.calls[0].prompt == "Drukarka nie drukuje"
    assert client.calls[0].system == "Jesteś parserem zgłoszeń."


async def test_running_out_of_scripted_answers_fails_loudly() -> None:
    """Sprawdza, czy przy jednej zaplanowanej odpowiedzi drugie wywołanie `complete()` kończy się
    wyjątkiem `LLMError`.

    Wyłapuje atrapę, która po wyczerpaniu scenariusza po cichu powtarza ostatnią odpowiedź: test nie
    zauważyłby wtedy, że kod zawołał model częściej, niż powinien."""
    client = FakeLLMClient(responses=["jedyna odpowiedź"])

    await client.complete("zgłoszenie 1")

    with pytest.raises(LLMError):
        await client.complete("zgłoszenie 2")


async def test_completion_reports_usage_for_the_log_line() -> None:
    """Sprawdza, czy odpowiedź atrapy niesie nazwę modelu `fake` i oba liczniki tokenów: 4 na
    wejściu (jedno słowo promptu systemowego i trzy słowa promptu) oraz 2 na wyjściu.

    Wyłapuje atrapę, która zostawia liczniki puste albo pomija prompt systemowy przy liczeniu
    wejścia: wpis rozliczenia w logu miałby wtedy na atrapie inny kształt niż u prawdziwego
    dostawcy."""
    client = FakeLLMClient(responses=["dwa slowa"])

    completion = await client.complete("trzy slowa razem", system="jeden")

    assert completion.model             == FAKE_MODEL_NAME
    assert completion.prompt_tokens     == 4   # „jeden" i trzy słowa promptu
    assert completion.completion_tokens == 2
    assert completion.latency_ms        >= 0


async def test_an_unscripted_turn_is_plain_text_without_tools() -> None:
    """Sprawdza, czy atrapa bez scenariusza tur odpowiada na `complete_turn()` samą odpowiedzią
    domyślną, bez żadnego wywołania narzędzia.

    Wyłapuje atrapę, która bez scenariusza zgłasza błąd albo sama wymyśla wywołanie narzędzia:
    przebieg na gołej atrapie przestałby być przewidywalny."""
    turn = await FakeLLMClient().complete_turn(SYSTEM, [USER], TOOLS)

    assert turn.message == ChatMessage(role="assistant", content=DEFAULT_FAKE_RESPONSE)


async def test_scripted_turns_are_returned_in_order() -> None:
    """Sprawdza, czy scenariusz dwóch tur (najpierw wyszukiwanie, potem odpowiedź) wraca w tej
    kolejności, a trzecie wywołanie kończy się wyjątkiem `LLMError`.

    Wyłapuje atrapę, która myli kolejność tur albo po wyczerpaniu scenariusza powtarza ostatnią:
    test nie zauważyłby wtedy, że kod zawołał model częściej, niż zakładał."""
    client = FakeLLMClient(turns=[SEARCH, ANSWER])

    first  = await client.complete_turn(SYSTEM, [USER], TOOLS)
    second = await client.complete_turn(SYSTEM, [USER, SEARCH], TOOLS)

    assert (first.message, second.message) == (SEARCH, ANSWER)

    with pytest.raises(LLMError):
        await client.complete_turn(SYSTEM, [USER], TOOLS)


async def test_every_turn_call_is_recorded_with_what_the_model_got() -> None:
    """Sprawdza, czy po jednej turze atrapa ma w `turn_calls` jeden wpis z promptem systemowym,
    rozmową i narzędziami, które dostała.

    Wyłapuje atrapę, która nie zapisuje tur albo gubi część wejścia: testy węzła `agent` czytają ten
    dziennik, żeby sprawdzić, co węzeł wysłał modelowi."""
    client = FakeLLMClient(turns=[ANSWER])

    await client.complete_turn(SYSTEM, [USER, SEARCH], TOOLS)

    assert len(client.turn_calls) == 1
    assert client.turn_calls[0].system   == SYSTEM
    assert client.turn_calls[0].messages == [USER, SEARCH]
    assert client.turn_calls[0].tools    == TOOLS


async def test_answers_and_turns_have_separate_scripts() -> None:
    """Sprawdza, czy scenariusz odpowiedzi i scenariusz tur są niezależne: po jednej turze
    `complete()` nadal oddaje swoją zaplanowaną odpowiedź, a każda z dwóch metod ma w swoim
    dzienniku jedno wywołanie.

    Wyłapuje atrapę ze wspólnym licznikiem albo wspólnym dziennikiem: tura zużywałaby wtedy
    odpowiedź zaplanowaną dla `complete()` i test dostawałby nie to, co zaplanował."""
    client = FakeLLMClient(responses=["tekst"], turns=[ANSWER])

    turn       = await client.complete_turn(SYSTEM, [USER], TOOLS)
    completion = await client.complete("prompt")

    assert turn.message    == ANSWER
    assert completion.text == "tekst"
    assert (len(client.calls), len(client.turn_calls)) == (1, 1)


async def test_a_turn_reports_one_call_that_costs_nothing() -> None:
    """Sprawdza, czy tura atrapy zgłasza jedno wywołanie modelu `fake`, tokeny policzone z wejścia
    (7) i z wyjścia (3) oraz koszt równy zero.

    Wyłapuje atrapę, która nie rozlicza tury albo przypisuje jej koszt: suma zużycia w przebiegu na
    atrapach pokazywałaby wtedy złą liczbę wywołań albo pieniądze, których nikt nie wydał."""
    client = FakeLLMClient(turns=[SEARCH])

    turn = await client.complete_turn("dwa slowa", [USER], TOOLS)

    assert turn.model                   == FAKE_MODEL_NAME
    assert turn.usage.calls             == 1
    assert turn.usage.prompt_tokens     == 7   # dwa słowa promptu systemowego i pięć zgłoszenia
    assert turn.usage.completion_tokens == 3   # nazwa narzędzia i jego argumenty
    assert turn.usage.cost_usd          == 0.0
    assert turn.latency_ms              >= 0
