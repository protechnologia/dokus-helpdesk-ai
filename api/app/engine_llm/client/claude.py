import re
import time
from collections.abc import Sequence
from typing import Any

# Three failure modes, kept apart because the caller's message names which one happened:
#   APITimeoutError    — the request outlived its timeout
#   APIConnectionError — could not establish a connection at all
#   APIStatusError     — provider answered, but with a non-2xx status
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
)

from app.engine_llm.base import LLMClient
from app.engine_llm.errors import LLMError
from app.engine_llm.models.completion import LLMCompletion
from app.engine_llm.models.messages import ChatMessage, ToolCall, ToolDefinition
from app.engine_llm.models.turn import LLMTurn
from app.engine_llm.models.usage import LLMUsage
from app.engine_llm.pricing.claude import calculate_cost_usd, price_of

# Ceiling on ONE answer, not a target. A parsed ticket is a small JSON object, but a thread with a
# quoted mail history can push the model into a long answer; cutting it off mid-JSON would waste
# the whole (already paid for) call, so the ceiling sits far above the expected size.
MAX_OUTPUT_TOKENS = 8_000

# Newer models REJECT the sampling parameters outright: sending `temperature` to Sonnet 5 returns
# `400 invalid_request_error: temperature is deprecated for this model`, while Haiku 4.5 still
# accepts it. Verified against the live API on 2026-08-01.
#
# The list holds the families that still take it, not the ones that refuse it, so a model released
# after this build defaults to NOT sending the parameter — a new model that quietly ignored an
# unsupported knob would be a worse outcome than one that never received it.
MODELS_ACCEPTING_TEMPERATURE = ("claude-haiku-4-5",)

# Cache promptu, włączony w każdym żądaniu. Jedno pole na górnym poziomie żądania: dostawca sam
# ustawia punkt cache i przesuwa go wraz z rozmową. Cache obejmuje POCZĄTEK żądania w kolejności
# narzędzia → prompt systemowy → wiadomości, więc w pętli z narzędziami cała dotychczasowa rozmowa
# jest odczytem (ułamek stawki wejścia), a pełną stawką płaci się tylko za to, co doszło.
# Czas życia 5 minut, odnawiany przy każdym odczycie. Cena: pierwszy zapis kosztuje 1,25 stawki
# wejścia — gdy ten sam początek nie wróci w ciągu 5 minut, płacimy te 25% za nic. Początki
# krótsze niż minimum modelu (512–4096 tokenów) nie są cache'owane wcale.
PROMPT_CACHE = {"type": "ephemeral"}

# Tura z narzędziami: model MA wywołać któreś narzędzie, nie odpowiedzieć tekstem. Każdy graf
# kończy się wywołaniem `respond_<graf>`, więc tura bez wywołania jest zawsze błędem formatu.
# Wymuszenie (`any`) przyjmują tylko starsze rodziny. Modele 5.5 odpowiadają na nie błędem
# `400 tool_choice: type "tool" and "any" are not supported for this model`, a `claude-sonnet-5`
# i `claude-opus-5` je przyjmują — sprawdzone na żywym API 2026-10-07. Modele spoza listy dostają
# `auto`: mogą wtedy odpowiedzieć samym tekstem, a taką turę odsyła do poprawki węzeł `respond`.
#
# Lista trzyma rodziny PRZYJMUJĄCE wymuszenie, jak `MODELS_ACCEPTING_TEMPERATURE`: `auto` przyjmuje
# każdy model, a odrzucone wymuszenie zatrzymuje każdą turę, więc nowy model domyślnie go nie
# dostaje. `claude-haiku-4-5` jest na liście za dokumentacją dostawcy, bez sprawdzenia na żywo.
MODELS_ACCEPTING_FORCED_TOOL_CALL = ("claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5")

TOOL_CHOICE_ANY  = {"type": "any"}
TOOL_CHOICE_AUTO = {"type": "auto"}

# Rodzaje bloków odpowiedzi, które klient czyta albo odsyła w ustalonym kształcie.
BLOCK_TEXT              = "text"
BLOCK_TOOL_USE          = "tool_use"
BLOCK_THINKING          = "thinking"
BLOCK_REDACTED_THINKING = "redacted_thinking"


def belongs_to_family(
    model:    str,              # np. "claude-haiku-4-5-20251001"
    families: tuple[str, ...],  # np. ("claude-haiku-4-5", "claude-sonnet-5")
) -> bool:
    """
    Description:
    Sprawdza, czy model należy do jednej z rodzin: nosi nazwę rodziny albo nazwę rodziny z datą
    wydania na końcu. Sam początek nazwy nie wystarcza, bo `claude-sonnet-5-5` zaczyna się od
    `claude-sonnet-5`, a to inna rodzina.

    Example args:
        model="claude-haiku-4-5-20251001"
        families=("claude-haiku-4-5", "claude-sonnet-5")

    Example result:
        True
    """
    return any(re.fullmatch(rf"{re.escape(family)}(-\d{{8}})?", model) for family in families)


class ClaudeLLMClient(LLMClient):
    """
    Description:
    Talks to the Claude API and is the ONLY module in this project allowed to import the Anthropic
    SDK (CLAUDE.md -> rule 4). Everything above it sees `LLMClient` and `LLMCompletion`, so
    swapping Claude for Bielik on RunPod is a configuration change, not a code change.

    Do czego:
    The Messages API is shaped differently from the OpenAI-compatible one this project will use
    for Bielik: the system prompt is a top-level argument rather than a message, answers arrive as
    a list of content blocks, and usage is reported over four token classes instead of two. Those
    differences are the reason this is a separate client rather than a branch inside a shared one
    (CLAUDE.md -> "Warstwa LLM").

    Flow:
        1. `get_llm_client()` builds it from `Settings`, failing fast when key or model is missing.
        2. `complete()` sends one prompt, with the system prompt passed as `system=`.
        3. The text blocks of the answer are joined, usage is read from `response.usage`, and the
           call is priced here — the price list is provider knowledge and stays on this side of
           the abstraction.
        4. `complete_turn()` robi to samo dla tury z narzędziami: `_build_turn_request()`
           tłumaczy rozmowę i narzędzia na kształt Messages API, a `_to_turn()` czyta
           z odpowiedzi wywołania narzędzi.

    Tura z narzędziami w tym API:

    | nasza wiadomość        | w żądaniu                                                     |
    |------------------------|---------------------------------------------------------------|
    | prompt systemowy       | pole `system`                                                 |
    | `user`                 | wiadomość `user` z tekstem                                    |
    | `assistant` od modelu  | wiadomość `assistant` z jego blokami (`provider_items`)       |
    | `assistant` bez nich   | blok `text` i bloki `tool_use` złożone z tekstu i wywołań     |
    | `tool`                 | blok `tool_result`; wyniki jednej tury w JEDNEJ wiadomości `user` |
    """

    def __init__(
        self,
        api_key:     str,          # e.g. "sk-ant-api03-...KLUCZ"
        model:       str,          # e.g. "claude-haiku-4-5"
        timeout:     float = 60.0, # seconds
        temperature: float = 0.0,  # ignored by models that no longer accept the parameter
    ):
        """
        Description:
        Builds the async SDK client and validates that the model has a known price. Pricing is
        checked HERE, at construction, rather than after the first answer comes back: discovering
        an unpriced model at that point means the call was already paid for.

        Whether `temperature` is sent at all is settled here too, because newer models reject the
        parameter with a 400 instead of ignoring it — see `MODELS_ACCEPTING_TEMPERATURE`.

        Tak samo rozstrzyga się tu, czy tura z narzędziami wymusza wywołanie narzędzia: nowsze
        modele odrzucają wymuszenie błędem 400 — patrz `MODELS_ACCEPTING_FORCED_TOOL_CALL`.

        Example args:
            api_key="sk-ant-api03-...KLUCZ"
            model="claude-haiku-4-5"
            timeout=60.0
            temperature=0.0

        Example result:
            ClaudeLLMClient ready to answer `complete()`, with its model's price row verified

        Raises:
            LLMConfigError: the model has no entry in the price table
        """
        # Fail now, while the exception can still name a configuration problem.
        price_of(model)

        self._model       = model
        self._temperature = temperature
        self._client      = AsyncAnthropic(api_key=api_key, timeout=timeout)

        # Decided once. A dated snapshot ("claude-haiku-4-5-20251001") must match its family, so
        # this is a prefix test rather than an exact membership check.
        self._accepts_temperature = model.startswith(MODELS_ACCEPTING_TEMPERATURE)

        # Też rozstrzygane raz. Tu początek nazwy nie wystarcza: `claude-sonnet-5-5` zaczyna się od
        # `claude-sonnet-5`, a wymuszenie przyjmuje tylko ten drugi.
        forces_tool_call  = belongs_to_family(model, MODELS_ACCEPTING_FORCED_TOOL_CALL)
        self._tool_choice = TOOL_CHOICE_ANY if forces_tool_call else TOOL_CHOICE_AUTO

    async def complete(
        self,
        prompt: str,                # e.g. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] Nie działa…"
        system: str | None = None,  # e.g. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Sends one prompt and returns the answer together with its usage and cost.

        Example args:
            prompt="ZGŁOSZENIE 33644\\nTemat: Błąd wysyłki\\n\\n[klient] Nie działa…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="claude-haiku-4-5", prompt_tokens=4820,
                          completion_tokens=640, latency_ms=3120.4, cost_usd=0.0080)

        Raises:
            LLMError: the provider timed out, was unreachable, refused the request, or answered
                with nothing usable
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
        zużyciem i kosztem. Wywołanie narzędzia jest wymuszane (`tool_choice: any`) tam, gdzie
        model to przyjmuje; pozostałe modele dostają `auto` i mogą odpowiedzieć samym tekstem.

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\nNie przychodzą…")]
            tools=[ToolDefinition(name="find_tickets_vector", …),
                   ToolDefinition(name="respond_search", …)]

        Example result:
            LLMTurn(message=ChatMessage(role="assistant",
                                        tool_calls=[ToolCall(name="find_tickets_vector", …)],
                                        provider_items=[{"type": "tool_use", …}]),
                    model="claude-sonnet-5", latency_ms=3120.4, usage=LLMUsage(calls=1, …))

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
        request: dict,  # np. {"model": "claude-haiku-4-5", "max_tokens": 8000, "messages": […]}
    ):
        """
        Description:
        Wysyła żądanie do Messages API i tłumaczy awarie SDK na `LLMError`. Wspólne dla
        `complete()` i `complete_turn()`, żeby oba mówiły o awarii tym samym komunikatem.

        Example args:
            request={"model": "claude-haiku-4-5", "max_tokens": 8000, "messages": […]}

        Example result:
            Message(content=[TextBlock(text="…")], usage=Usage(input_tokens=4820, …))

        Raises:
            LLMError: dostawca nie odpowiedział w czasie, był nieosiągalny albo odrzucił żądanie
        """
        try:
            response = await self._client.messages.create(**request)
        except APITimeoutError as exc:
            # Ran past the deadline: the request may or may not have been processed on their side.
            raise LLMError(f"przekroczono limit czasu wywołania modelu {self._model}") from exc
        except APIConnectionError as exc:
            # Never reached the provider at all — network, DNS or a wrong base URL.
            raise LLMError(f"brak połączenia z API modelu {self._model}") from exc
        except APIStatusError as exc:
            # Reached them and was refused: bad key, unknown model, rate limit, provider outage.
            # Only the status code goes into our message; the body may quote the prompt back, and
            # the prompt carries customer data (CLAUDE.md -> "Logi i obserwowalność").
            raise LLMError(
                f"API modelu {self._model} odrzuciło żądanie (HTTP {exc.status_code})"
            ) from exc

        return response

    def _build_request(
        self,
        prompt: str,         # np. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] Nie działa…"
        system: str | None,  # np. "Jesteś parserem zgłoszeń helpdesku."
    ) -> dict:
        """
        Description:
        Składa żądanie do Messages API. Wydzielone z `complete()`, bo jest czyste: test sprawdza
        kształt żądania bez sieci i bez klucza.

        Example args:
            prompt="ZGŁOSZENIE 33644\nTemat: Błąd wysyłki\n\n[klient] Nie działa…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            {"model": "claude-haiku-4-5", "max_tokens": 1500,
             "cache_control": {"type": "ephemeral"},
             "messages": [{"role": "user", "content": "ZGŁOSZENIE 33644…"}],
             "temperature": 0.0, "system": "Jesteś parserem…"}
        """
        # Prompt systemowy jest w tym API argumentem NA GÓRNYM POZIOMIE, a nie wiadomością o roli
        # „system": podany jako wiadomość byłby czytany jak tekst użytkownika i osłabiłby każdą
        # instrukcję. Gdy go nie ma, pole pomijamy — jawne None jest odrzucane.
        request: dict = {
            "model":         self._model,
            "max_tokens":    MAX_OUTPUT_TOKENS,
            "cache_control": PROMPT_CACHE,
            "messages":      [{"role": "user", "content": prompt}],
        }

        # Wysyłane tylko tam, gdzie nadal jest przyjmowane — gdzie indziej to twarde 400.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        if system is not None:
            request["system"] = system

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

        Cache promptu jest włączony tak samo jak w `complete()`. Obejmuje początek żądania
        w kolejności narzędzia → prompt systemowy → wiadomości, więc narzędzia idą w kolejności,
        w jakiej przyszły: ten sam początek co do znaku w każdej turze.

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\nNie przychodzą…")]
            tools=[ToolDefinition(name="respond_search", description="Kończy.", parameters={…})]

        Example result:
            {"model": "claude-sonnet-5", "max_tokens": 8000, "cache_control": {"type": "ephemeral"},
             "system": "Jesteś asystentem…",
             "messages": [{"role": "user", "content": "=== ZGŁOSZENIE ===…"}],
             "tools": [{"name": "respond_search", "description": "Kończy.", "input_schema": {…}}],
             "tool_choice": {"type": "any"}}
        """
        request: dict = {
            "model":         self._model,
            "max_tokens":    MAX_OUTPUT_TOKENS,
            "cache_control": PROMPT_CACHE,
            "system":        system,
            "messages":      self._turn_messages(messages),
            "tools":         [self._tool_param(tool) for tool in tools],
            "tool_choice":   self._tool_choice,
        }

        # Wysyłane tylko tam, gdzie nadal jest przyjmowane — gdzie indziej to twarde 400.
        if self._accepts_temperature:
            request["temperature"] = self._temperature

        return request

    @staticmethod
    def _tool_param(
        tool: ToolDefinition,  # np. ToolDefinition(name="read_docs", description="…", …)
    ) -> dict:
        """
        Description:
        Zapisuje definicję narzędzia w kształcie tego API: schemat argumentów idzie pod nazwą
        `input_schema`.

        Example args:
            tool=ToolDefinition(name="read_docs", description="Czyta sekcje.", parameters={…})

        Example result:
            {"name": "read_docs", "description": "Czyta sekcje.", "input_schema": {…}}
        """
        param = {
            "name":         tool.name,
            "description":  tool.description,
            "input_schema": tool.parameters,
        }

        return param

    def _turn_messages(
        self,
        messages: Sequence[ChatMessage],  # np. [ChatMessage(role="user", …), …]
    ) -> list[dict]:
        """
        Description:
        Tłumaczy rozmowę na wiadomości Messages API. W tym API nie ma roli `tool`: wynik
        narzędzia to blok `tool_result` w wiadomości `user`, a wyniki wszystkich wywołań z jednej
        tury modelu muszą stać w JEDNEJ takiej wiadomości, zaraz po tej turze.

        Example args:
            messages=[ChatMessage(role="user", content="Nie przychodzą przesyłki"),
                      ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="toolu_1", …)]),
                      ChatMessage(role="tool", call_id="toolu_1", content='{"tickets": []}')]

        Example result:
            [{"role": "user", "content": "Nie przychodzą przesyłki"},
             {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_1", …}]},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1",
                                           "content": '{"tickets": []}'}]}]
        """
        translated: list[dict] = []

        for message in messages:
            # --- tura użytkownika ---
            if message.role == "user":
                translated.append({"role": "user", "content": message.content})
                continue

            # --- tura modelu ---
            if message.role == "assistant":
                translated.append({"role": "assistant", "content": self._assistant_blocks(message)})
                continue

            # --- wynik narzędzia: dokładany do wiadomości z wynikami tej samej tury modelu ---
            block  = {
                "type":        "tool_result",
                "tool_use_id": message.call_id,
                "content":     message.content,
            }
            latest = translated[-1] if translated else None

            if latest and latest["role"] == "user" and isinstance(latest["content"], list):
                latest["content"].append(block)
                continue

            translated.append({"role": "user", "content": [block]})

        return translated

    @staticmethod
    def _assistant_blocks(
        message: ChatMessage,  # np. ChatMessage(role="assistant", tool_calls=[ToolCall(…)])
    ) -> list[dict]:
        """
        Description:
        Bloki jednej tury modelu. Turę, która przyszła od tego dostawcy, odsyłamy jego blokami
        (`provider_items`): mogą w nich być bloki myślenia z podpisem, których nie wolno zmieniać.
        Turę bez nich — z atrapy albo od innego dostawcy — składamy z tekstu i wywołań.

        Example args:
            message=ChatMessage(role="assistant", content="Sprawdzę.",
                                tool_calls=[ToolCall(call_id="toolu_1", name="read_docs", …)])

        Example result:
            [{"type": "text", "text": "Sprawdzę."},
             {"type": "tool_use", "id": "toolu_1", "name": "read_docs", "input": {…}}]
        """
        if message.provider_items:
            return list(message.provider_items)

        blocks: list[dict] = []

        if message.content:
            blocks.append({"type": BLOCK_TEXT, "text": message.content})

        blocks.extend(
            {
                "type":  BLOCK_TOOL_USE,
                "id":    call.call_id,
                "name":  call.name,
                "input": call.arguments,
            }
            for call in message.tool_calls
        )

        return blocks

    def _to_turn(
        self,
        response,           # np. Message(content=[ToolUseBlock(id="toolu_1", …)], usage=Usage(…))
        elapsed_ms: float,  # np. 3120.4
    ) -> LLMTurn:
        """
        Description:
        Przepisuje jedną odpowiedź SDK na turę modelu w naszym kształcie. Wydzielone, bo czyste:
        test podaje atrapę odpowiedzi i sprawdza mapowanie bez sieci i bez klucza.

        Example args:
            response=Message(content=[ToolUseBlock(id="toolu_1", name="read_docs", input={…})], …)
            elapsed_ms=3120.4

        Example result:
            LLMTurn(message=ChatMessage(role="assistant", tool_calls=[ToolCall(…)],
                                        provider_items=[{"type": "tool_use", …}]),
                    model="claude-sonnet-5", latency_ms=3120.4, usage=LLMUsage(calls=1, …))

        Raises:
            LLMError: tura nie ma ani tekstu, ani wywołań narzędzi, albo argumenty wywołania nie
                są obiektem
        """
        calls = [
            ToolCall(
                call_id   = block.id,
                name      = block.name,
                arguments = self._arguments_of(block),
            )
            for block in response.content
            if block.type == BLOCK_TOOL_USE
        ]
        text = "".join(block.text for block in response.content if block.type == BLOCK_TEXT)

        # Model nic nie napisał i niczego nie wywołał.
        if not calls and not text:
            raise LLMError(
                f"tura modelu nie zawiera tekstu ani wywołań narzędzi "
                f"(stop_reason={response.stop_reason})"
            )

        message = ChatMessage(
            role           = "assistant",
            content        = text,
            tool_calls     = calls,
            provider_items = [self._block_to_item(block) for block in response.content],
        )

        turn = LLMTurn(
            message    = message,
            model      = response.model,
            latency_ms = elapsed_ms,
            usage      = self._usage(response),
        )

        return turn

    @staticmethod
    def _arguments_of(
        block,  # np. ToolUseBlock(id="toolu_1", name="read_docs", input={"section_ids": ["a"]})
    ) -> dict[str, Any]:
        """
        Description:
        Argumenty wywołania narzędzia z bloku `tool_use`. To API podaje je już jako obiekt, nie
        jako tekst JSON, więc zostaje tylko sprawdzić, że to słownik.

        Example args:
            block=ToolUseBlock(id="toolu_1", name="read_docs", input={"section_ids": ["a"]})

        Example result:
            {"section_ids": ["a"]}

        Raises:
            LLMError: argumenty nie są obiektem
        """
        if not isinstance(block.input, dict):
            raise LLMError(
                f"model podał argumenty narzędzia `{block.name}`, które nie są obiektem JSON"
            )

        return dict(block.input)

    @staticmethod
    def _block_to_item(
        block,  # np. ToolUseBlock(type="tool_use", id="toolu_1", name="read_docs", input={…})
    ) -> dict[str, Any]:
        """
        Description:
        Zapisuje blok odpowiedzi w kształcie, w jakim to API przyjmuje go z powrotem w następnej
        turze. Znane rodzaje bloków są przepisywane pole po polu, bo odpowiedź niesie też pola,
        których żądanie nie przyjmuje; blok nieznanego rodzaju idzie w całości.

        | rodzaj bloku        | co wraca do dostawcy                      |
        |---------------------|-------------------------------------------|
        | `text`              | tekst                                     |
        | `tool_use`          | identyfikator, nazwa i argumenty          |
        | `thinking`          | treść myślenia i jej podpis, bez zmian    |
        | `redacted_thinking` | zaszyfrowane dane, bez zmian              |

        Example args:
            block=ToolUseBlock(type="tool_use", id="toolu_1", name="read_docs", input={…})

        Example result:
            {"type": "tool_use", "id": "toolu_1", "name": "read_docs", "input": {…}}
        """
        # --- tekst modelu ---
        if block.type == BLOCK_TEXT:
            return {"type": BLOCK_TEXT, "text": block.text}

        # --- wywołanie narzędzia ---
        if block.type == BLOCK_TOOL_USE:
            return {
                "type":  BLOCK_TOOL_USE,
                "id":    block.id,
                "name":  block.name,
                "input": block.input,
            }

        # --- myślenie: podpis poświadcza treść, więc oba idą nietknięte ---
        if block.type == BLOCK_THINKING:
            return {
                "type":      BLOCK_THINKING,
                "thinking":  block.thinking,
                "signature": block.signature,
            }

        # --- myślenie ukryte przez dostawcę ---
        if block.type == BLOCK_REDACTED_THINKING:
            return {"type": BLOCK_REDACTED_THINKING, "data": block.data}

        # --- rodzaj, którego ten klient nie zna: bez pól pustych ---
        return block.model_dump(mode="json", exclude_none=True)

    def _to_completion(
        self,
        response,           # e.g. anthropic.types.Message with content=[TextBlock(text="{…}")]
        elapsed_ms: float,  # e.g. 3120.4
    ) -> LLMCompletion:
        """
        Description:
        Maps one SDK answer onto our own contract and prices it. Split out from `complete()`
        because it is pure: a test can feed it a stub response and assert the mapping without a
        network call and without an API key.

        Example args:
            response=Message(content=[TextBlock(text='{"problem": "…"}')], usage=Usage(…))
            elapsed_ms=3120.4

        Example result:
            LLMCompletion(text='{"problem": "…"}', model="claude-haiku-4-5", cost_usd=0.0080, …)

        Raises:
            LLMError: the answer carried no text block (the model stopped before writing anything)
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
        response,  # np. Message(model="claude-haiku-4-5", usage=Usage(input_tokens=4820, …))
    ) -> LLMUsage:
        """
        Description:
        Czyta zużycie jednego wywołania w czterech klasach tokenów i wycenia je. Wspólne dla
        `complete()` i `complete_turn()`: oba płacą według tych samych liczników. W tym API klasy
        są rozłączne od razu — `input_tokens` to samo świeże wejście.

        Example args:
            response=Message(model="claude-haiku-4-5", usage=Usage(input_tokens=4820, …))

        Example result:
            LLMUsage(calls=1, prompt_tokens=4820, completion_tokens=640, cost_usd=0.0080)
        """
        usage = response.usage

        # Cache counters are absent on SDK versions that do not report them, and `None` on a call
        # that used no caching; treat both as zero rather than letting `None` reach the arithmetic.
        cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read_tokens  = getattr(usage, "cache_read_input_tokens", 0) or 0

        # Priced against the model the response REPORTS, not the one we asked for. The two normally
        # match, but when they do not, the bill follows what actually ran.
        counted = LLMUsage(
            calls              = 1,
            prompt_tokens      = usage.input_tokens,
            completion_tokens  = usage.output_tokens,
            cache_write_tokens = cache_write_tokens,
            cache_read_tokens  = cache_read_tokens,
            cost_usd           = calculate_cost_usd(
                model              = response.model,
                prompt_tokens      = usage.input_tokens,
                completion_tokens  = usage.output_tokens,
                cache_write_tokens = cache_write_tokens,
                cache_read_tokens  = cache_read_tokens,
            ),
        )

        return counted

    @staticmethod
    def _extract_text(response) -> str:  # e.g. Message(content=[TextBlock(text='{"problem": …}')])
        """
        Description:
        Joins the text blocks of one answer. The answer is a LIST of blocks, not a string, and
        non-text blocks may appear among them — reading `content[0].text` blindly would raise on
        the first answer that opens with anything else.

        Example args:
            response=Message(content=[TextBlock(text='{"problem": "Brak tonera"}')])

        Example result:
            '{"problem": "Brak tonera"}'

        Raises:
            LLMError: no text block in the answer — nothing for the caller to parse
        """
        parts = [block.text for block in response.content if block.type == "text"]

        if not parts:
            raise LLMError(
                f"odpowiedź modelu nie zawiera tekstu (stop_reason={response.stop_reason})"
            )

        return "".join(parts)
