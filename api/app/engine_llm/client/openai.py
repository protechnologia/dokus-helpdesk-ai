import time

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
        2. `complete()` składa żądanie (`_build_request()`), woła dostawcę i tłumaczy jego błędy.
        3. `_to_completion()` czyta tekst, rozdziela zużycie na cztery ROZŁĄCZNE klasy tokenów
           i wycenia wywołanie — cennik to wiedza dostawcy i zostaje po tej stronie.
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

        # --- wywołanie dostawcy ---
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

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        completion = self._to_completion(response, elapsed_ms)

        self._log_call(prompt, completion)

        return completion

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
        return LLMCompletion(
            text               = text,
            model              = response.model,
            prompt_tokens      = fresh_tokens,
            completion_tokens  = usage.output_tokens,
            cache_write_tokens = cache_write_tokens,
            cache_read_tokens  = cache_read_tokens,
            latency_ms         = elapsed_ms,
            cost_usd           = calculate_cost_usd(
                model              = response.model,
                prompt_tokens      = fresh_tokens,
                completion_tokens  = usage.output_tokens,
                cache_write_tokens = cache_write_tokens,
                cache_read_tokens  = cache_read_tokens,
            ),
        )

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
