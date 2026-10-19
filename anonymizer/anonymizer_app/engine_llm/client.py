import logging
import time
from collections.abc import Sequence
from typing import Any

import httpx

from anonymizer_app.core_errors.engine_config_error import EngineConfigError
from anonymizer_app.core_errors.llm_error import LLMError
from anonymizer_app.core_model.chat_message import ChatMessage
from anonymizer_app.core_model.llm_answer import LLMAnswer

logger = logging.getLogger(__name__)

# Ścieżka Chat Completions względem adresu z `LLM_ANONYMIZATION_BASE_URL`, który kończy się na
# `/v1` — tak jak go podaje vLLM i Ollama.
CHAT_COMPLETIONS_PATH = "/chat/completions"

# Statusy, które znaczą złą konfigurację, a nie chwilową awarię: odrzucony klucz i nieznany model
# albo zły adres. Czekanie ich nie naprawi, więc nie stają się 503.
CONFIG_STATUSES = (401, 403, 404)

# `finish_reason`, przy którym odpowiedź urwał limit tokenów.
TRUNCATED_FINISH_REASON = "length"


class LLMClient:
    """
    Description:
    Klient modelu anonimizującego: jedno wywołanie Chat Completions zgodnego z OpenAI (vLLM,
    Ollama), ze schematem JSON odpowiedzi. „Klient", bo przekracza granicę procesu — model stoi na
    osobnym serwerze z GPU (CLAUDE.md -> „Warstwy kodu").

    Do czego:
    Silnik `agent` woła go z każdego węzła, który pyta model: osoby i adresy. Usługa nie dzieli kodu
    z klientem modelu w `api`, a różnica jest celowa: tamten zapisuje prompt i odpowiedź na DEBUG,
    a tu promptem jest surowe zgłoszenie, którego nie wolno zapisać na żadnym poziomie. Do logu
    idą same liczby.

    Flow:
        1. Fabryka silnika buduje go raz na proces z adresem, modelem i limitem czasu.
        2. `complete_json()` wysyła prompt systemowy, rozmowę i schemat odpowiedzi, a oddaje treść
           z informacją, czy limit tokenów ją uciął.
        3. Awaria transportu albo odpowiedź spoza kontraktu to `LLMError` (503), odmowa, która
           znaczy złą konfigurację — `EngineConfigError`.
        4. `aclose()` zamyka połączenia przy wyłączaniu usługi.

    Schemat odpowiedzi idzie w `response_format` (`json_schema`): serwer dekoduje tylko tokeny,
    które go spełniają, więc odpowiedź jest JSON-em, dopóki limit tokenów jej nie utnie.
    """

    def __init__(
        self,
        base_url:    str,                # np. "https://…-8000.proxy.runpod.net/v1"
        model:       str,                # np. "speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"
        api_key:     str | None = None,  # np. None — vLLM bez `--api-key` klucza nie sprawdza
        temperature: float      = 0.0,   # wskazywanie danych ma być powtarzalne
        timeout:     float      = 60.0,  # sekundy na jedno wywołanie
    ):
        """
        Description:
        Buduje klienta jednego serwera modelu. Z modelem się nie łączy: endpoint z GPU bywa
        chwilowo wyłączony, a usługa ma wtedy wstać i odpowiadać 503, a nie padać przy starcie.

        Example args:
            base_url="https://…-8000.proxy.runpod.net/v1"
            model="speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"
            api_key=None
            temperature=0.0
            timeout=60.0

        Example result:
            LLMClient wysyłający do https://…/v1/chat/completions
        """
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        self._model       = model
        self._temperature = temperature
        self._client      = httpx.AsyncClient(
            base_url = base_url.rstrip("/"),  # ukośnik na końcu zdublowałby się ze ścieżką
            headers  = headers,
            timeout  = timeout,
        )

    async def complete_json(
        self,
        system:      str,                    # np. "Jesteś narzędziem do anonimizacji…"
        messages:    Sequence[ChatMessage],  # przykłady z promptu i na końcu tekst do przejrzenia
        schema_name: str,                    # np. "osoby" — nazwa schematu w żądaniu
        schema:      dict[str, Any],         # np. {"type": "object", "properties": {"dane": …}}
        max_tokens:  int,                    # np. 1500 — limit odpowiedzi
    ) -> LLMAnswer:
        """
        Description:
        Wysyła jedną rozmowę ze schematem odpowiedzi i oddaje treść odpowiedzi. Jedyne miejsce,
        w którym awarie transportu stają się błędami usługi, więc nikt wyżej nie widzi typów
        `httpx`.

        Example args:
            system="Jesteś narzędziem do anonimizacji zgłoszeń helpdesku. Wypisz…"
            messages=[ChatMessage(role="user", content="===\\nOd: Leszek Dudziak…\\n===")]
            schema_name="osoby"
            schema={"type": "object", "properties": {"dane": {…}}, "required": ["dane"]}
            max_tokens=1500

        Example result:
            LLMAnswer(content='{"dane": [{"tekst": "Leszek", "rodzaj": "IMIĘ"}]}',
                      truncated=False, prompt_tokens=1840, completion_tokens=32,
                      latency_ms=2140.5)

        Raises:
            EngineConfigError: serwer odrzucił klucz albo nie zna modelu lub adresu
            LLMError: serwer nie odpowiedział w czasie, był nieosiągalny, odpowiedział innym
                błędem albo treścią spoza kontraktu Chat Completions
        """
        request = self._build_request(system, messages, schema_name, schema, max_tokens)

        started_at = time.perf_counter()
        response   = await self._send(request)
        latency_ms = (time.perf_counter() - started_at) * 1000

        answer = self._read_answer(response, latency_ms)

        # Same liczby, na każdym poziomie logu: w prompcie stoi surowe zgłoszenie, a w odpowiedzi
        # jego fragmenty.
        logger.info(
            "llm_call model=%s schema=%s prompt_tokens=%d completion_tokens=%d truncated=%s "
            "latency_ms=%.1f",
            self._model,
            schema_name,
            answer.prompt_tokens,
            answer.completion_tokens,
            answer.truncated,
            answer.latency_ms,
        )

        return answer

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenia. Woła to usługa przy wyłączaniu; powtórne wywołanie nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._client.aclose()

    def _build_request(
        self,
        system:      str,                    # np. "Jesteś narzędziem do anonimizacji…"
        messages:    Sequence[ChatMessage],  # np. [ChatMessage(role="user", content="===…")]
        schema_name: str,                    # np. "adresy"
        schema:      dict[str, Any],         # np. {"type": "object", …}
        max_tokens:  int,                    # np. 300
    ) -> dict[str, Any]:
        """
        Description:
        Składa żądanie Chat Completions: prompt systemowy jako pierwsza wiadomość, rozmowa po nim
        i schemat odpowiedzi w `response_format`. Wydzielone, bo czyste: test sprawdza kształt
        żądania bez serwera.

        Example args:
            system="Jesteś narzędziem…"
            messages=[ChatMessage(role="user", content="===\\nTekst\\n===")]
            schema_name="adresy"
            schema={"type": "object", "properties": {"adresy": {…}}, "required": ["adresy"]}
            max_tokens=300

        Example result:
            {"model": "speakleash/…", "temperature": 0.0, "max_tokens": 300,
             "messages": [{"role": "system", "content": "Jesteś narzędziem…"},
                          {"role": "user", "content": "===\\nTekst\\n==="}],
             "response_format": {"type": "json_schema",
                                 "json_schema": {"name": "adresy", "schema": {…}}}}
        """
        # `max_tokens`, a nie nowsze `max_completion_tokens`: vLLM i Ollama przyjmują oba, a ta
        # pisownia działa także na starszych wersjach serwerów.
        request = {
            "model":           self._model,
            "temperature":     self._temperature,
            "max_tokens":      max_tokens,
            "messages":        [
                {"role": "system", "content": system},
                *(message.model_dump() for message in messages),
            ],
            "response_format": {
                "type":        "json_schema",
                "json_schema": {"name": schema_name, "schema": schema},
            },
        }

        return request

    async def _send(
        self,
        request: dict[str, Any],  # np. {"model": "speakleash/…", "messages": […], …}
    ) -> httpx.Response:
        """
        Description:
        Wysyła żądanie i tłumaczy awarie transportu na błędy usługi. Komunikaty nie cytują treści
        odpowiedzi: serwer modelu potrafi zacytować w błędzie fragment wejścia.

        Example args:
            request={"model": "speakleash/…", "messages": […], "max_tokens": 300, …}

        Example result:
            <Response [200 OK]>

        Raises:
            EngineConfigError: odpowiedź 401, 403 albo 404 — klucz, model albo adres
            LLMError: brak odpowiedzi w czasie, brak połączenia albo inny status spoza 2xx
        """
        try:
            response = await self._client.post(CHAT_COMPLETIONS_PATH, json=request)
            response.raise_for_status()
        except httpx.TimeoutException as exc:  # model nie odpowiedział w limicie czasu
            raise LLMError(
                f"model {self._model} nie odpowiedział w limicie czasu "
                f"(LLM_ANONYMIZATION_TIMEOUT_SECONDS)"
            ) from exc
        except httpx.HTTPStatusError as exc:   # serwer odpowiedział statusem spoza 2xx
            status = exc.response.status_code

            # Klucz, nazwa modelu albo adres: poprawia się konfigurację, nie czeka.
            if status in CONFIG_STATUSES:
                raise EngineConfigError(
                    f"serwer modelu odrzucił żądanie (HTTP {status}); sprawdź "
                    f"LLM_ANONYMIZATION_BASE_URL, LLM_ANONYMIZATION_MODEL "
                    f"i LLM_ANONYMIZATION_API_KEY"
                ) from exc

            raise LLMError(f"serwer modelu odpowiedział HTTP {status}") from exc
        except httpx.HTTPError as exc:         # odmowa połączenia, DNS, zerwany transport
            raise LLMError(
                f"brak połączenia z serwerem modelu pod {self._client.base_url}"
            ) from exc

        return response

    @staticmethod
    def _read_answer(
        response:   httpx.Response,  # np. 200 z {"choices": [{"message": {…}, …}], "usage": {…}}
        latency_ms: float,           # np. 2140.5
    ) -> LLMAnswer:
        """
        Description:
        Czyta treść, powód zakończenia i zużycie z udanej odpowiedzi Chat Completions.

        Example args:
            response=<Response [200 OK]>
            latency_ms=2140.5

        Example result:
            LLMAnswer(content='{"adresy": []}', truncated=False, prompt_tokens=950,
                      completion_tokens=6, latency_ms=2140.5)

        Raises:
            LLMError: treść nie jest JSON-em albo nie ma wyboru z tekstem odpowiedzi
        """
        try:
            payload = response.json()
            choice  = payload["choices"][0]
            content = choice["message"]["content"]
            usage   = payload.get("usage") or {}
        except (
            ValueError,  # treść spoza JSON-a — zwykle strona błędu pośrednika
            KeyError,    # JSON bez wyboru albo bez wiadomości
            IndexError,  # pusta lista wyborów
            TypeError,   # pole innego typu niż w kontrakcie
        ) as exc:
            raise LLMError("serwer modelu odpowiedział treścią spoza kontraktu") from exc

        if not isinstance(content, str):
            raise LLMError("odpowiedź modelu nie ma tekstu")

        answer = LLMAnswer(
            content           = content,
            truncated         = choice.get("finish_reason") == TRUNCATED_FINISH_REASON,
            prompt_tokens     = usage.get("prompt_tokens") or 0,
            completion_tokens = usage.get("completion_tokens") or 0,
            latency_ms        = latency_ms,
        )

        return answer
