import logging

import httpx
import pytest

from anonymizer_app.core_errors.engine_config_error import EngineConfigError
from anonymizer_app.core_errors.llm_error import LLMError
from anonymizer_app.core_model.chat_message import ChatMessage
from anonymizer_app.engine_llm import LLMClient
from tests._helpers.anonymization import RAW_TEXT, SENSITIVE
from tests._helpers.anonymizer_llm import MODEL_BASE_URL, MODEL_NAME, chat_answer, model_client_on
from tests._helpers.transport import always, capturing, raising

# Rozmowa jednego wywołania: sam tekst zgłoszenia, jak ostatnia wiadomość węzła.
MESSAGES = [ChatMessage(role="user", content=f"===\n{RAW_TEXT}\n===")]

# Schemat odpowiedzi węzła adresów, w skrócie.
SCHEMA = {"type": "object", "properties": {"adresy": {"type": "array"}}, "required": ["adresy"]}


async def ask(
    client: LLMClient,  # np. model_client_on(always(chat_answer('{"adresy": []}')))
) -> object:
    """
    Description:
    Jedno wywołanie klienta z rozmową i schematem testu.

    Example args:
        client=model_client_on(always(chat_answer('{"adresy": []}')))

    Example result:
        LLMAnswer(content='{"adresy": []}', truncated=False, …)
    """
    return await client.complete_json("Jesteś narzędziem…", MESSAGES, "adresy", SCHEMA, 300)


async def test_the_request_carries_the_conversation_and_the_schema() -> None:
    """Sprawdza, czy żądanie idzie na `/v1/chat/completions` z modelem, temperaturą, limitem
    tokenów, promptem systemowym jako pierwszą wiadomością, rozmową po nim i schematem odpowiedzi
    w `response_format` (`json_schema` z nazwą).

    Wyłapuje żądanie bez schematu (serwer oddałby tekst zamiast JSON-a i każda odpowiedź byłaby
    błędem), bez limitu tokenów (zapętlona odpowiedź ciągnęłaby się minutami) albo z rozmową bez
    promptu systemowego."""
    seen: list = []
    client = model_client_on(capturing(seen, {
        ("POST", "/v1/chat/completions"): httpx.Response(200, json=chat_answer('{"adresy": []}')),
    }))

    await ask(client)

    body = seen[0]["body"]

    assert seen[0]["path"]        == "/v1/chat/completions"
    assert body["model"]          == MODEL_NAME
    assert body["temperature"]    == 0.0
    assert body["max_tokens"]     == 300
    assert body["messages"][0]    == {"role": "system", "content": "Jesteś narzędziem…"}
    assert body["messages"][1:]   == [message.model_dump() for message in MESSAGES]
    assert body["response_format"] == {
        "type":        "json_schema",
        "json_schema": {"name": "adresy", "schema": SCHEMA},
    }


@pytest.mark.parametrize(
    ("api_key", "expected"),
    [(None, None), ("sk-test", "Bearer sk-test")],
    ids=["bez-klucza", "z-kluczem"],
)
async def test_the_key_goes_in_the_header_only_when_given(
    api_key:  str | None,
    expected: str | None,
) -> None:
    """Sprawdza, czy klient ma nagłówek `Authorization` tylko wtedy, gdy podano klucz, i wtedy
    w postaci `Bearer <klucz>`.

    Wyłapuje pusty nagłówek, który serwer bez `--api-key` może odrzucić, i klucz, który nie
    dociera do serwera z `--api-key`. Sprawdza nagłówki klienta `httpx`, bo atrapa transportu
    z `with_transport()` buduje go od nowa, bez nich."""
    client = LLMClient(base_url=MODEL_BASE_URL, model=MODEL_NAME, api_key=api_key)

    assert client._client.headers.get("Authorization") == expected

    await client.aclose()


@pytest.mark.parametrize(
    ("finish_reason", "truncated"),
    [("stop", False), ("length", True)],
    ids=["pełna", "ucięta"],
)
async def test_the_answer_carries_content_usage_and_truncation(
    finish_reason: str,
    truncated:     bool,
) -> None:
    """Sprawdza, czy odpowiedź niesie treść, zużycie tokenów i to, czy limit ją uciął: ucięta
    jest wtedy i tylko wtedy, gdy `finish_reason` to „length”.

    Wyłapuje uciętą odpowiedź oznaczoną jako pełną: niepełny JSON byłby wtedy błędem, a pełne
    elementy sprzed ucięcia przepadłyby razem z danymi, które wskazywały."""
    answer_body = chat_answer('{"adresy": []}', finish_reason, 950, 6)
    answer      = await ask(model_client_on(always(answer_body)))

    assert answer.content           == '{"adresy": []}'
    assert answer.truncated         is truncated
    assert answer.prompt_tokens     == 950
    assert answer.completion_tokens == 6


@pytest.mark.parametrize("status", [401, 403, 404], ids=["401", "403", "404"])
async def test_a_refusal_meaning_bad_config_is_a_config_error(status: int) -> None:
    """Sprawdza, czy odrzucony klucz (401, 403) i nieznany model albo adres (404) kończą się
    błędem konfiguracji, który nazywa zmienne do poprawienia.

    Wyłapuje złą konfigurację podaną jako 503: wołający czekałby na coś, czego czekanie nie
    naprawi, a vLLM odpowiada 404 na literówkę w nazwie modelu."""
    with pytest.raises(EngineConfigError) as caught:
        await ask(model_client_on(always({"error": "nope"}, status=status)))

    assert "LLM_ANONYMIZATION_MODEL" in str(caught.value)


@pytest.mark.parametrize(
    "transport",
    [
        pytest.param(always({"error": "busy"}, status=502), id="502"),
        pytest.param(raising(httpx.ConnectError("refused")), id="brak-połączenia"),
        pytest.param(raising(httpx.ReadTimeout("slow")), id="limit-czasu"),
        pytest.param(always(text="<html>proxy</html>"), id="html"),
        pytest.param(always({"choices": []}), id="bez-wyborów"),
        pytest.param(always({"choices": [{"message": {"content": None}}]}), id="bez-tekstu"),
    ],
)
async def test_a_transport_failure_is_an_llm_error(transport: httpx.MockTransport) -> None:
    """Sprawdza, czy wyłączony pod (502 pośrednika), brak połączenia, limit czasu, strona HTML
    zamiast JSON-a, odpowiedź bez wyborów i wybór bez tekstu kończą się `LLMError`, czyli 503
    i zatrzymaniem grafu w `api`.

    Wyłapuje typ `httpx` wypuszczony poza klienta (trasa oddałaby 500 zamiast 503) i odpowiedź
    spoza kontraktu przyjętą jako pusta — pusta lista znaczyłaby „w tekście nie ma danych”."""
    with pytest.raises(LLMError):
        await ask(model_client_on(transport))


async def test_neither_the_text_nor_the_answer_reach_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sprawdza, czy na żadnym poziomie logu, także DEBUG, nie ma fragmentu zgłoszenia ani
    odpowiedzi modelu z tymi fragmentami — jest jeden wpis z liczbami.

    Wyłapuje powrót zapisu treści na DEBUG, jak w kliencie modelu w `api`: tu promptem jest
    surowe zgłoszenie, a odpowiedzią — jego dane osobowe."""
    caplog.set_level(logging.DEBUG)
    answer = chat_answer('{"dane": [{"tekst": "Nowak", "rodzaj": "NAZWISKO"}]}')

    await ask(model_client_on(always(answer)))

    for fragment in SENSITIVE:
        assert fragment not in caplog.text
    assert "llm_call" in caplog.text
