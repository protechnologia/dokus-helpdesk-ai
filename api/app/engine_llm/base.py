import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.engine_llm.errors import LLMError
from app.engine_llm.models.completion import LLMCompletion
from app.engine_llm.models.messages import ChatMessage, ToolDefinition
from app.engine_llm.models.turn import LLMTurn

logger = logging.getLogger(__name__)

# Wpis rozliczenia jednego wywołania modelu — ten sam dla `complete()` i `complete_turn()`.
USAGE_LOG_FORMAT = (
    "llm_call model=%s prompt_tokens=%d completion_tokens=%d "
    "cache_write_tokens=%d cache_read_tokens=%d latency_ms=%.1f cost_usd=%.6f"
)


class LLMClient(ABC):
    """
    Description:
    Jedyna droga, którą reszta aplikacji rozmawia z modelem językowym. Każda podklasa opakowuje
    jednego dostawcę i jest JEDYNYM miejscem, w którym wolno importować jego SDK (CLAUDE.md ->
    zasada 4), więc zmiana dostawcy to zmiana konfiguracji, nie kodu.

    Do czego:
    Dwie metody na dwa sposoby rozmowy z modelem:

    | metoda            | co robi                                                          |
    |-------------------|------------------------------------------------------------------|
    | `complete()`      | jeden prompt → jeden tekst                                       |
    | `complete_turn()` | rozmowa i narzędzia → jedna tura: tekst albo wywołania narzędzi  |

    Flow:
        1. `get_llm_client()` (`factory.py`) buduje implementację wskazaną przez dostawcę z
           kompletu ustawień roli (`LLM_GENERATION_PROVIDER` albo `LLM_ANONYMIZATION_PROVIDER`)
           i odmawia, gdy jej konfiguracja jest niepełna.
        2. Wołający podaje gotowy prompt (`complete()`) albo rozmowę z narzędziami
           (`complete_turn()`, woła ją węzeł `agent`).
        3. Implementacja woła dostawcę, tłumaczy odpowiedź na nasz kształt i zgłasza zużycie przez
           `_log_call()` albo `_log_turn()`, żeby każdy dostawca dawał ten sam wpis w logu.

    Klient wykonuje JEDNO wywołanie i niczego nie pamięta. Pętla — kolejne tury i wykonanie
    narzędzi — należy do grafu: w kliencie wyniki narzędzi omijałyby granicę anonimizacji,
    a zmiana dostawcy zmieniałaby zachowanie pętli.

    Implementacje są asynchroniczne i mają jawny limit czasu: zawieszony model nie może trzymać
    żądania bez końca.
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,                # np. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        system: str | None = None,  # np. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Wysyła jeden prompt i oddaje odpowiedź modelu. Bez rozmowy i bez narzędzi.

        Example args:
            prompt="Zgłoszenie klienta:\\n\\nDrukarka nie drukuje…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="gpt-6.1-sol", prompt_tokens=482, …)

        Raises:
            LLMError: dostawca odmówił, nie odpowiedział w czasie albo odpowiedział czymś, czego
                nie da się użyć
        """

    @abstractmethod
    async def complete_turn(
        self,
        system:   str,                       # np. "Jesteś asystentem wdrożeniowca helpdesku…"
        messages: Sequence[ChatMessage],     # rozmowa: zgłoszenie, tury modelu, wyniki narzędzi
        tools:    Sequence[ToolDefinition],  # narzędzia, które model może wywołać w tej turze
    ) -> LLMTurn:
        """
        Description:
        Wykonuje jedną turę modelu w rozmowie z narzędziami: model dostaje prompt systemowy,
        dotychczasową rozmowę i narzędzia, a odpowiada tekstem albo wywołaniami narzędzi. Klient
        niczego nie wykonuje — narzędzia uruchamia graf, a wyniki wracają w `messages` następnej
        tury.

        Format wiadomości i narzędzi u dostawcy tłumaczy klient, w obie strony. To, co dostawca
        każe odesłać bez zmian (rozumowanie, bloki myślenia), klient zostawia w `provider_items`
        zwracanej wiadomości i sam stamtąd czyta, gdy ta wiadomość wraca w `messages`.

        Model ma w każdej turze wywołać narzędzie: także odpowiedź końcowa przychodzi narzędziem
        (`respond_<graf>`). Klient wymusza to u dostawcy, który na to pozwala; gdzie się nie da,
        tura z samym tekstem wraca jak każda inna i rozstrzyga ją graf.

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\\nNie przychodzą…")]
            tools=[ToolDefinition(name="find_tickets_vector", …),
                   ToolDefinition(name="respond_search", …)]

        Example result:
            LLMTurn(message=ChatMessage(role="assistant",
                                        tool_calls=[ToolCall(name="find_tickets_vector", …)]),
                    model="gpt-6.1-sol", latency_ms=3120.4, usage=LLMUsage(calls=1, …))

        Raises:
            LLMError: dostawca odmówił, nie odpowiedział w czasie albo odpowiedział turą, której
                nie da się użyć (bez tekstu i bez wywołań, z argumentami niebędącymi JSON-em)
        """

    @staticmethod
    def _parse_arguments(
        tool_name: str,  # np. "find_tickets_vector"
        raw:       str,  # np. '{"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}'
    ) -> dict[str, Any]:
        """
        Description:
        Zamienia argumenty wywołania narzędzia z tekstu JSON, w jakim podają je dostawcy mówiący
        protokołem OpenAI, na słownik. Czy argumenty są POPRAWNE, sprawdza dopiero klasa
        argumentów narzędzia w węźle `run_tools`; tutaj chodzi tylko o to, żeby dało się je
        w ogóle zapisać w `ToolCall`. Puste argumenty to pusty słownik.

        Example args:
            tool_name="find_tickets_vector"
            raw='{"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}'

        Example result:
            {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}

        Raises:
            LLMError: tekst nie jest JSON-em albo nie jest obiektem
        """
        # --- narzędzie bez argumentów: dostawca bywa, że podaje pusty tekst ---
        if not raw.strip():
            return {}

        try:
            arguments = json.loads(raw)
        except json.JSONDecodeError:
            # Bez treści: argumenty powstały ze zgłoszenia, czyli z danych klienta.
            raise LLMError(
                f"model podał argumenty narzędzia `{tool_name}`, które nie są JSON-em"
            ) from None

        if not isinstance(arguments, dict):
            raise LLMError(
                f"model podał argumenty narzędzia `{tool_name}`, które nie są obiektem JSON"
            )

        return arguments

    def _log_call(
        self,
        prompt:     str,            # np. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        completion: LLMCompletion,  # np. LLMCompletion(text="…", model="fake", …)
    ) -> None:
        """
        Description:
        Zapisuje rozliczenie jednego wywołania `complete()`, w jednym kształcie dla każdego
        dostawcy. Prompt i odpowiedź idą wyłącznie na DEBUG — oba niosą dane klienta (CLAUDE.md ->
        „Logi i obserwowalność"); na INFO są same identyfikatory i liczby.

        Example args:
            prompt="Zgłoszenie klienta:…"
            completion=LLMCompletion(text="…", model="fake", prompt_tokens=12, …)

        Example result:
            None — jeden wpis INFO ze zużyciem, jeden DEBUG z tekstami
        """
        logger.info(
            USAGE_LOG_FORMAT,
            completion.model,
            completion.prompt_tokens,
            completion.completion_tokens,
            completion.cache_write_tokens,
            completion.cache_read_tokens,
            completion.latency_ms,
            completion.cost_usd,
        )
        logger.debug("llm_call prompt=%r response=%r", prompt, completion.text)

    def _log_turn(
        self,
        messages: Sequence[ChatMessage],  # rozmowa wysłana do modelu
        turn:     LLMTurn,                # np. LLMTurn(message=ChatMessage(…), model="fake", …)
    ) -> None:
        """
        Description:
        Zapisuje rozliczenie jednego wywołania `complete_turn()` — tym samym wpisem INFO co
        `_log_call()`. Rozmowa i tura modelu idą wyłącznie na DEBUG, bo niosą dane klienta.

        Example args:
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===…")]
            turn=LLMTurn(message=ChatMessage(role="assistant", …), model="fake", …)

        Example result:
            None — jeden wpis INFO ze zużyciem, jeden DEBUG z rozmową i turą
        """
        logger.info(
            USAGE_LOG_FORMAT,
            turn.model,
            turn.usage.prompt_tokens,
            turn.usage.completion_tokens,
            turn.usage.cache_write_tokens,
            turn.usage.cache_read_tokens,
            turn.latency_ms,
            turn.usage.cost_usd,
        )
        logger.debug("llm_call messages=%r turn=%r", list(messages), turn.message)
