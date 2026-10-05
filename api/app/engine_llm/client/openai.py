import json
import time
from collections.abc import Sequence

# Trzy rodzaje awarii, trzymane osobno, bo komunikat dla wołającego nazywa, która zaszła:
#   APITimeoutError    — żądanie trwało dłużej niż limit czasu
#   APIConnectionError — nie udało się nawiązać połączenia
#   APIStatusError     — dostawca odpowiedział, ale statusem spoza 2xx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
)

from app.engine_llm.base import LLMClient
from app.engine_llm.errors import LLMError
from app.engine_llm.models.completion import LLMCompletion
from app.engine_llm.models.messages import ChatMessage, ToolCall, ToolDefinition
from app.engine_llm.models.turn import LLMTurn
from app.engine_llm.models.usage import LLMUsage
from app.engine_llm.pricing.openai import calculate_cost_usd, price_of

# Sufit JEDNEJ odpowiedzi, nie cel. Stoi daleko ponad rozmiarem karty zgłoszenia, bo modele
# rozumujące zużywają część tego budżetu na tokeny, których wołający nie widzi: wyczerpanie go
# w połowie JSON-u marnuje całe, już opłacone wywołanie.
MAX_OUTPUT_TOKENS = 8_000

# Rodziny, które PRZYJMUJĄ `temperature`. Pozostałe odpowiadają na ten parametr twardym 400, a nie
# ostrzeżeniem. Sprawdzone na żywym API 2026-10-04, po jednym wywołaniu na każdy model z cennika:
# przyjmują tylko gpt-5.4 i gpt-4.1 (z wariantami mini i nano); odrzucają gpt-6, gpt-5.6, gpt-5.5
# i o4-mini.
#
# Lista wymienia rodziny przyjmujące, nie odrzucające, żeby model wydany po tym kodzie domyślnie
# parametru NIE dostał: nowe rodziny są rozumujące, a żądanie odrzucone przez nieznany parametr
# jest gorsze niż pominięty parametr. Ten sam kierunek co w `client/claude.py`.
MODELS_ACCEPTING_TEMPERATURE = ("gpt-5.4", "gpt-4.1")

# Tura z narzędziami: model MA wywołać narzędzie, nie odpowiedzieć tekstem. Każdy graf kończy się
# wywołaniem `respond_<graf>`, więc tura bez wywołania jest zawsze błędem formatu.
TOOL_CHOICE_REQUIRED = "required"

# Żądanie nie jest przechowywane u dostawcy (`store: False`), więc rozumowanie modelu nie zostaje
# po jego stronie. Dostawca oddaje je wtedy w postaci zaszyfrowanej, a my odsyłamy je w następnej
# turze razem z resztą odpowiedzi: bez tego model rozumujący zaczynałby każdą turę od zera.
INCLUDE_ENCRYPTED_REASONING = ["reasoning.encrypted_content"]

# Rodzaj elementu odpowiedzi, który jest wywołaniem narzędzia.
ITEM_FUNCTION_CALL = "function_call"


class OpenAILLMClient(LLMClient):
    """
    Description:
    Rozmawia z API Responses OpenAI i jest JEDYNYM modułem, który importuje SDK OpenAI
    (CLAUDE.md -> zasada 4). Wszystko powyżej widzi `LLMClient` i `LLMCompletion`.

    Do czego:
    API Responses, a nie Chat Completions, bo najnowsze rodziny (gpt-6.1-sol) nie przyjmują
    w Chat Completions narzędzi, a tura z narzędziami ma stanąć na tym samym kliencie. Na API
    Responses odpowiada każdy model z cennika, także starsze (gpt-4.1, o4-mini, gpt-5.4) —
    sprawdzone na żywym API 2026-10-04.

    Osobny klient, a nie gałąź w `ClaudeLLMClient`, bo oba API różnią się KSZTAŁTEM żądania:
    tu prompt systemowy to pole `instructions`, odpowiedź to lista elementów (rozumowanie,
    wiadomość), a tokeny cache przychodzą WEWNĄTRZ licznika wejścia.

    Endpointy zgodne z OpenAI (Ollama, vLLM, RunPod) mówią Chat Completions i idą przez
    `client/ollama.py`. `base_url` jest tu dla pośrednika, który mówi API Responses.

    Flow:
        1. `get_llm_client()` buduje klienta z `Settings`; brak klucza, modelu albo ceny modelu
           to błąd przy budowie.
        2. `complete()` składa żądanie (`_build_request()`), woła dostawcę (`_send()`) i czyta
           tekst (`_to_completion()`).
        3. `complete_turn()` robi to samo dla tury z narzędziami: `_build_turn_request()`
           tłumaczy rozmowę i narzędzia na elementy tego API, a `_to_turn()` czyta z odpowiedzi
           wywołania narzędzi.
        4. `_usage()` rozdziela zużycie na cztery ROZŁĄCZNE klasy tokenów i wycenia wywołanie —
           cennik to wiedza dostawcy i zostaje po tej stronie.

    Tura z narzędziami w tym API:

    | nasza wiadomość        | element żądania                                              |
    |------------------------|--------------------------------------------------------------|
    | prompt systemowy       | pole `instructions`                                          |
    | `user`                 | `{"role": "user", "content": …}`                             |
    | `assistant` od modelu  | elementy jego odpowiedzi odesłane bez zmian (`provider_items`) |
    | `assistant` bez nich   | tekst jako wiadomość, wywołania jako `function_call`         |
    | `tool`                 | `{"type": "function_call_output", "call_id": …, "output": …}` |
    """

    def __init__(
        self,
        api_key:     str,                 # np. "sk-proj-...KLUCZ"
        model:       str,                 # np. "gpt-6.1-sol"
        base_url:    str | None = None,   # np. "https://proxy.example/v1"
        timeout:     float      = 60.0,   # sekundy
        temperature: float      = 0.0,    # pomijana dla modeli, które jej nie przyjmują
    ):
        """
        Description:
        Buduje asynchronicznego klienta SDK i sprawdza, czy model ma cenę. Cena jest sprawdzana
        TUTAJ, przy budowie, a nie po pierwszej odpowiedzi: model bez ceny wykryty wtedy oznacza
        wywołanie już opłacone.

        Tu też zapada, czy `temperature` w ogóle idzie w żądaniu, bo większość modeli odrzuca ją
        błędem 400 zamiast pominąć — patrz `MODELS_ACCEPTING_TEMPERATURE`.

        Example args:
            api_key="sk-proj-...KLUCZ"
            model="gpt-6.1-sol"
            base_url=None
            timeout=60.0
            temperature=0.0

        Example result:
            OpenAILLMClient gotowy na `complete()`, z potwierdzonym wierszem cennika modelu

        Raises:
            LLMConfigError: modelu nie ma w cenniku
        """
        # Błąd teraz, póki wyjątek może jeszcze nazwać problem konfiguracji.
        price_of(model)

        self._model       = model
        self._temperature = temperature

        # `base_url=None` zostawia SDK jego adres domyślny; pusty string wysłałby żądanie pod
        # zepsuty adres (CLAUDE.md -> „Pułapki": pusty string zamiast braku).
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout)

        # Rozstrzygane raz. Snapshot z datą („gpt-5.4-mini-2026-03-17") ma pasować do swojej
        # rodziny, stąd test przedrostka, a nie dokładnej nazwy.
        self._accepts_temperature = model.startswith(MODELS_ACCEPTING_TEMPERATURE)

    async def complete(
        self,
        prompt: str,                # np. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] Nie działa…"
        system: str | None = None,  # np. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Wysyła jeden prompt i oddaje odpowiedź razem ze zużyciem i kosztem.

        Example args:
            prompt="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki\\n\\n[klient] Nie działa…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="gpt-6.1-sol", prompt_tokens=4820,
                          completion_tokens=640, latency_ms=3120.4, cost_usd=0.0160)

        Raises:
            LLMError: dostawca nie odpowiedział w czasie, był nieosiągalny, odrzucił żądanie
                albo odpowiedział bez tekstu
        """
        started_at = time.perf_counter()
        request    = self._build_request(prompt, system)
        response   = await self._send(request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        completion = self._to_completion(response, elapsed_ms)

        self._log_call(prompt, completion)

        return completion

    async def complete_turn(
        self,
        system:   str,                       # np. "Jesteś asystentem wdrożeniowca helpdesku…"
        messages: Sequence[ChatMessage],     # rozmowa: zgłoszenie, tury modelu, wyniki narzędzi
        tools:    Sequence[ToolDefinition],  # narzędzia, które model może wywołać w tej turze
    ) -> LLMTurn:
        """
        Description:
        Wykonuje jedną turę modelu w rozmowie z narzędziami i oddaje ją w naszym kształcie, ze
        zużyciem i kosztem. Model musi wywołać narzędzie (`tool_choice: required`).

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\nNie przychodzą…")]
            tools=[ToolDefinition(name="find_tickets_vector", …),
                   ToolDefinition(name="respond_search", …)]

        Example result:
            LLMTurn(message=ChatMessage(role="assistant",
                                        tool_calls=[ToolCall(name="find_tickets_vector", …)],
                                        provider_items=[{"type": "reasoning", …}, …]),
                    model="gpt-6.1-sol", latency_ms=3120.4, usage=LLMUsage(calls=1, …))

        Raises:
            LLMError: dostawca nie odpowiedział w czasie, był nieosiągalny, odrzucił żądanie
                albo odpowiedział turą bez tekstu i bez wywołań
        """
        started_at = time.perf_counter()
        request    = self._build_turn_request(system, messages, tools)
        response   = await self._send(request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        turn       = self._to_turn(response, elapsed_ms)

        self._log_turn(messages, turn)

        return turn

    async def _send(
        self,
        request: dict,  # np. {"model": "gpt-6.1-sol", "input": "…", "store": False, …}
    ):
        """
        Description:
        Wysyła żądanie do API Responses i tłumaczy awarie SDK na `LLMError`. Wspólne dla
        `complete()` i `complete_turn()`, żeby oba mówiły o awarii tym samym komunikatem.

        Example args:
            request={"model": "gpt-6.1-sol", "input": "ZGŁOSZENIE 33644…", "store": False}

        Example result:
            Response(output=[…], usage=ResponseUsage(input_tokens=4820, …))

        Raises:
            LLMError: dostawca nie odpowiedział w czasie, był nieosiągalny albo odrzucił żądanie
        """
        try:
            response = await self._client.responses.create(**request)
        except APITimeoutError as exc:
            # Po terminie: żądanie mogło zostać po tamtej stronie przetworzone albo nie.
            raise LLMError(f"przekroczono limit czasu wywołania modelu {self._model}") from exc
        except APIConnectionError as exc:
            # W ogóle nie dotarliśmy do dostawcy — sieć, DNS albo zły adres bazowy.
            raise LLMError(f"brak połączenia z API modelu {self._model}") from exc
        except APIStatusError as exc:
            # Dotarliśmy i dostaliśmy odmowę: zły klucz, nieznany model, limit, awaria dostawcy.
            # Do komunikatu idzie sam kod statusu; treść odpowiedzi potrafi zacytować prompt,
            # a prompt niesie dane klienta (CLAUDE.md -> „Logi i obserwowalność").
            raise LLMError(
                f"API modelu {self._model} odrzuciło żądanie (HTTP {exc.status_code})"
            ) from exc

        return response

    def _build_request(
        self,
        prompt: str,         # np. "ZGŁOSZENIE 33644\nTemat: …"
        system: str | None,  # np. "Jesteś parserem zgłoszeń helpdesku."
    ) -> dict:
        """
        Description:
        Składa żądanie do API Responses. Wydzielone, bo czyste: test sprawdza kształt żądania bez
        sieci i bez klucza.

        Example args:
            prompt="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            {"model": "gpt-6.1-sol", "input": "ZGŁOSZENIE 33644…", "max_output_tokens": 8000,
             "store": False, "instructions": "Jesteś parserem zgłoszeń helpdesku."}
        """
        request: dict = {
            "model":             self._model,
            "input":             prompt,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            # To API domyślnie PRZECHOWUJE odpowiedzi u dostawcy przez 30 dni, żeby dało się do
            # nich wracać po identyfikatorze. Nie wracamy, a w prompcie są dane klienta.
            "store":             False,
        }

        # Prompt systemowy jest tu osobnym polem, nie wiadomością.
        if system is not None:
            request["instructions"] = system

        # Tylko tam, gdzie jest przyjmowana — u pozostałych modeli to twarde 400.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        return request

    def _build_turn_request(
        self,
        system:   str,                       # np. "Jesteś asystentem wdrożeniowca helpdesku…"
        messages: Sequence[ChatMessage],     # rozmowa w naszym kształcie
        tools:    Sequence[ToolDefinition],  # narzędzia grafu, z `respond_<graf>` na końcu
    ) -> dict:
        """
        Description:
        Składa żądanie tury z narzędziami. Wydzielone, bo czyste: test sprawdza kształt żądania
        bez sieci i bez klucza.

        Kolejność pól nie ma znaczenia dla API, ale treść początku żądania — narzędzia, prompt
        systemowy, pierwsze wiadomości — musi być w każdej turze identyczna co do znaku, bo na
        niej stoi cache promptu dostawcy. Dlatego narzędzia idą w kolejności, w jakiej przyszły.

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\nNie przychodzą…")]
            tools=[ToolDefinition(name="respond_search", description="Kończy.", parameters={…})]

        Example result:
            {"model": "gpt-6.1-sol", "instructions": "Jesteś asystentem…",
             "input": [{"role": "user", "content": "=== ZGŁOSZENIE ===…"}],
             "tools": [{"type": "function", "name": "respond_search", "description": "Kończy.",
                        "parameters": {…}, "strict": False}],
             "tool_choice": "required", "max_output_tokens": 8000, "store": False,
             "include": ["reasoning.encrypted_content"]}
        """
        request: dict = {
            "model":             self._model,
            "instructions":      system,
            "input":             self._input_items(messages),
            "tools":             [self._tool_param(tool) for tool in tools],
            "tool_choice":       TOOL_CHOICE_REQUIRED,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            # Jak w `complete()`: w rozmowie są dane klienta, więc nic nie zostaje u dostawcy.
            "store":             False,
            "include":           INCLUDE_ENCRYPTED_REASONING,
        }

        # Tylko tam, gdzie jest przyjmowana — u pozostałych modeli to twarde 400.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        return request

    @staticmethod
    def _tool_param(
        tool: ToolDefinition,  # np. ToolDefinition(name="read_docs", description="…", …)
    ) -> dict:
        """
        Description:
        Zapisuje definicję narzędzia w kształcie tego API. Tryb `strict` jest wyłączony jawnie,
        bo to API domyślnie go włącza, a wtedy wymaga schematu, w którym każde pole jest
        wymagane. Nasze schematy takie nie są; argumenty i tak waliduje klasa argumentów
        narzędzia w węźle `run_tools`.

        Example args:
            tool=ToolDefinition(name="read_docs", description="Czyta sekcje.", parameters={…})

        Example result:
            {"type": "function", "name": "read_docs", "description": "Czyta sekcje.",
             "parameters": {…}, "strict": False}
        """
        param = {
            "type":        "function",
            "name":        tool.name,
            "description": tool.description,
            "parameters":  tool.parameters,
            "strict":      False,
        }

        return param

    @staticmethod
    def _input_items(
        messages: Sequence[ChatMessage],  # np. [ChatMessage(role="user", …), …]
    ) -> list[dict]:
        """
        Description:
        Tłumaczy rozmowę na elementy wejścia API Responses, w tej samej kolejności.

        Turę modelu, która przyszła od tego dostawcy, odsyłamy tak, jak ją oddał
        (`provider_items`): są w niej elementy rozumowania w postaci zaszyfrowanej, a ich
        kolejność względem wywołań narzędzi ma znaczenie. Turę bez tych elementów — z atrapy
        albo od innego dostawcy — składamy z tekstu i wywołań.

        Example args:
            messages=[ChatMessage(role="user", content="Nie przychodzą przesyłki"),
                      ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="call_1", …)]),
                      ChatMessage(role="tool", call_id="call_1", content='{"tickets": []}')]

        Example result:
            [{"role": "user", "content": "Nie przychodzą przesyłki"},
             {"type": "function_call", "call_id": "call_1", "name": "find_tickets_vector",
              "arguments": '{"problem": "…"}'},
             {"type": "function_call_output", "call_id": "call_1", "output": '{"tickets": []}'}]
        """
        items: list[dict] = []

        for message in messages:
            # --- wynik narzędzia: wskazuje wywołanie, na które odpowiada ---
            if message.role == "tool":
                items.append({
                    "type":    "function_call_output",
                    "call_id": message.call_id,
                    "output":  message.content,
                })
                continue

            # --- tura użytkownika ---
            if message.role == "user":
                items.append({"role": "user", "content": message.content})
                continue

            # --- tura modelu od tego dostawcy: bez zmian, razem z rozumowaniem ---
            if message.provider_items:
                items.extend(message.provider_items)
                continue

            # --- tura modelu bez elementów dostawcy: tekst, potem wywołania ---
            if message.content:
                items.append({"role": "assistant", "content": message.content})

            items.extend(
                {
                    "type":      ITEM_FUNCTION_CALL,
                    "call_id":   call.call_id,
                    "name":      call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                }
                for call in message.tool_calls
            )

        return items

    def _to_turn(
        self,
        response,           # np. Response(output=[ResponseFunctionToolCall(…)], usage=…)
        elapsed_ms: float,  # np. 3120.4
    ) -> LLMTurn:
        """
        Description:
        Przepisuje jedną odpowiedź SDK na turę modelu w naszym kształcie. Wydzielone, bo czyste:
        test podaje atrapę odpowiedzi i sprawdza mapowanie bez sieci i bez klucza.

        Wszystkie elementy odpowiedzi zostają w `provider_items`, żeby następna tura mogła je
        odesłać bez zmian.

        Example args:
            response=Response(output=[ResponseReasoningItem(…), ResponseFunctionToolCall(…)], …)
            elapsed_ms=3120.4

        Example result:
            LLMTurn(message=ChatMessage(role="assistant", tool_calls=[ToolCall(…)],
                                        provider_items=[{"type": "reasoning", …}, …]),
                    model="gpt-6.1-sol", latency_ms=3120.4, usage=LLMUsage(calls=1, …))

        Raises:
            LLMError: tura nie ma ani tekstu, ani wywołań narzędzi, albo argumenty wywołania nie
                są obiektem JSON
        """
        calls = [
            ToolCall(
                call_id   = item.call_id,
                name      = item.name,
                arguments = self._parse_arguments(item.name, item.arguments),
            )
            for item in response.output
            if item.type == ITEM_FUNCTION_CALL
        ]
        text = response.output_text or ""

        # Model nic nie napisał i niczego nie wywołał: odmówił albo zużył budżet na rozumowanie.
        if not calls and not text:
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)

            raise LLMError(
                f"tura modelu nie zawiera tekstu ani wywołań narzędzi "
                f"(status={response.status}, powód={reason})"
            )

        message = ChatMessage(
            role           = "assistant",
            content        = text,
            tool_calls     = calls,
            # `exclude_none`: pola, których dostawca nie wypełnił, nie wracają do niego jako null.
            provider_items = [
                item.model_dump(mode="json", exclude_none=True) for item in response.output
            ],
        )

        turn = LLMTurn(
            message    = message,
            model      = response.model,
            latency_ms = elapsed_ms,
            usage      = self._usage(response),
        )

        return turn

    def _to_completion(
        self,
        response,           # np. Response(output=[…], usage=ResponseUsage(input_tokens=4820, …))
        elapsed_ms: float,  # np. 3120.4
    ) -> LLMCompletion:
        """
        Description:
        Przepisuje jedną odpowiedź SDK na nasz kontrakt i wycenia ją. Wydzielone z `complete()`,
        bo czyste: test podaje atrapę odpowiedzi i sprawdza mapowanie bez sieci i bez klucza.

        Example args:
            response=Response(output=[…], usage=ResponseUsage(input_tokens=4820, …))
            elapsed_ms=3120.4

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="gpt-6.1-sol", cost_usd=0.0160, …)

        Raises:
            LLMError: odpowiedź nie zawiera tekstu (model skończył, zanim cokolwiek napisał)
        """
        text  = self._extract_text(response)
        usage = self._usage(response)

        completion = LLMCompletion(
            text               = text,
            model              = response.model,
            prompt_tokens      = usage.prompt_tokens,
            completion_tokens  = usage.completion_tokens,
            cache_write_tokens = usage.cache_write_tokens,
            cache_read_tokens  = usage.cache_read_tokens,
            latency_ms         = elapsed_ms,
            cost_usd           = usage.cost_usd,
        )

        return completion

    @staticmethod
    def _usage(
        response,  # np. Response(model="gpt-6.1-sol", usage=ResponseUsage(input_tokens=4820, …))
    ) -> LLMUsage:
        """
        Description:
        Czyta zużycie jednego wywołania, rozdziela je na cztery rozłączne klasy tokenów i wycenia.
        Wspólne dla `complete()` i `complete_turn()`: oba płacą według tych samych liczników.

        Example args:
            response=Response(model="gpt-6.1-sol", usage=ResponseUsage(input_tokens=4820, …))

        Example result:
            LLMUsage(calls=1, prompt_tokens=2990, completion_tokens=640, cache_read_tokens=1830,
                     cost_usd=0.0160)
        """
        usage = response.usage

        # Liczniki cache przychodzą zagnieżdżone, a przy wywołaniu bez cache bywa, że nie ma
        # całej gałęzi; każdy brakujący poziom to zero, żeby `None` nie doszło do rachunku.
        details            = getattr(usage, "input_tokens_details", None)
        cache_read_tokens  = getattr(details, "cached_tokens", 0) or 0
        cache_write_tokens = getattr(details, "cache_write_tokens", 0) or 0

        # W tym API obie klasy cache siedzą WEWNĄTRZ `input_tokens`. Odejmujemy je, żeby cztery
        # klasy tokenów były rozłączne jak u Claude'a: cennik liczy każdą po swojej stawce,
        # a suma w `LLMUsage` znaczy to samo u każdego dostawcy. Dolna granica zero, bo rachunek
        # nie może wyjść ujemny, gdyby liczniki się nie zgadzały.
        fresh_tokens = max(usage.input_tokens - cache_read_tokens - cache_write_tokens, 0)

        # Cena modelu, który odpowiedź PODAJE, nie tego, o który prosiliśmy. Zwykle to ten sam,
        # a gdy nie — rachunek idzie za tym, co faktycznie policzyło. `output_tokens` obejmuje
        # tokeny rozumowania: za myślenie się płaci, po stawce wyjścia.
        counted = LLMUsage(
            calls              = 1,
            prompt_tokens      = fresh_tokens,
            completion_tokens  = usage.output_tokens,
            cache_write_tokens = cache_write_tokens,
            cache_read_tokens  = cache_read_tokens,
            cost_usd           = calculate_cost_usd(
                model              = response.model,
                prompt_tokens      = fresh_tokens,
                completion_tokens  = usage.output_tokens,
                cache_write_tokens = cache_write_tokens,
                cache_read_tokens  = cache_read_tokens,
            ),
        )

        return counted

    @staticmethod
    def _extract_text(response) -> str:  # np. Response(output=[ResponseOutputMessage(…)])
        """
        Description:
        Czyta tekst odpowiedzi. `output_text` to tekst sklejony przez SDK ze wszystkich
        wiadomości w odpowiedzi; jest pusty, gdy model nic nie napisał — odmówił albo zużył cały
        budżet na rozumowanie — i wtedy zgłaszamy błąd, zamiast oddawać tekst, którego nikt nie
        sparsuje.

        Example args:
            response=Response(output=[ResponseOutputMessage(content=[…'{"problem": "…"}'…])])

        Example result:
            '{"problem": "…"}'

        Raises:
            LLMError: odpowiedź nie zawiera tekstu
        """
        text = response.output_text

        if not text:
            # Powód jest tylko przy odpowiedzi niedokończonej, np. „max_output_tokens".
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)

            raise LLMError(
                f"odpowiedź modelu nie zawiera tekstu (status={response.status}, powód={reason})"
            )

        return text
