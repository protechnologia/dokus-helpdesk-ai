import json
import time
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.engine_llm.base import LLMClient
from app.engine_llm.errors import LLMError
from app.engine_llm.models.completion import LLMCompletion
from app.engine_llm.models.messages import ChatMessage, ToolDefinition
from app.engine_llm.models.turn import LLMTurn
from app.engine_llm.models.usage import LLMUsage

# Odpowiedź, gdy nikt nie zaplanował własnej. Stała, a nie echo promptu, żeby test, który
# przypadkiem na niej polega, padł głośno.
DEFAULT_FAKE_RESPONSE = "fake-llm-response"

FAKE_MODEL_NAME = "fake"


class LLMCall(BaseModel):
    """
    Description:
    Jedno zapisane wywołanie `FakeLLMClient.complete()`. Test sprawdza po nim, CO poszło do
    modelu (czy szablon dostał zgłoszenie, czy doszedł prompt systemowy), bez sięgania do pól
    prywatnych.
    """

    prompt: str         = Field(examples=["Zgłoszenie klienta:\n\nDrukarka nie drukuje…"])
    system: str | None  = Field(default=None, examples=["Jesteś parserem zgłoszeń helpdesku."])


class LLMTurnCall(BaseModel):
    """
    Description:
    Jedno zapisane wywołanie `FakeLLMClient.complete_turn()`: prompt systemowy, rozmowa i narzędzia,
    które model dostał w tej turze.
    """

    system:   str                  = Field(examples=["Jesteś asystentem wdrożeniowca helpdesku…"])
    messages: list[ChatMessage]
    tools:    list[ToolDefinition]


class FakeLLMClient(LLMClient):
    """
    Description:
    Atrapa modelu: implementacja domyślna obu ról (dostawca `fake`) i ta, na której chodzą testy.
    Niczego nigdzie nie wysyła, więc `docker compose up` i `pytest` nic nie kosztują i działają
    offline (CLAUDE.md -> „Warstwa LLM").

    Do czego:
    Scenariusz podany w konstruktorze pozwala testowi przeprowadzić kod przez wybrane odpowiedzi
    modelu: teksty dla `complete()` (`responses`) i tury rozmowy z narzędziami dla
    `complete_turn()` (`turns`). Oba scenariusze są niezależne.

    Flow:
        1. Test (albo fabryka) tworzy atrapę, opcjonalnie ze scenariuszem.
        2. Każde wywołanie zapisuje, co dostało (`calls`, `turn_calls`), i oddaje kolejną pozycję
           scenariusza; bez scenariusza — stałą odpowiedź domyślną.
        3. Wyczerpany scenariusz to błąd, nie powtórka: kod pod testem zawołał model częściej,
           niż test zakładał.
    """

    def __init__(
        self,
        responses: Sequence[str] | None = None,          # np. ['{"problem": "Brak tonera"}']
        turns:     Sequence[ChatMessage] | None = None,  # np. [tool_call_turn("find_docs_text", …)]
    ):
        """
        Description:
        Przyjmuje scenariusz i zakłada dzienniki wywołań.

        Example args:
            responses=['{"problem": "Brak tonera"}', '{"problem": "Zacięcie papieru"}']
            turns=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="respond_search", …)])]

        Example result:
            FakeLLMClient oddający te odpowiedzi i tury po kolei, z wywołaniami w `calls`
            i `turn_calls`
        """
        self._responses:     list[str] = list(responses) if responses is not None else []
        self._next_response: int       = 0

        self._turns:     list[ChatMessage] = list(turns) if turns is not None else []
        self._next_turn: int               = 0

        # Publiczne celowo: asercje je czytają, więc należą do kontraktu tej klasy.
        self.calls:      list[LLMCall]     = []
        self.turn_calls: list[LLMTurnCall] = []

    async def complete(
        self,
        prompt: str,                # np. "Zgłoszenie klienta:\n\nDrukarka nie drukuje…"
        system: str | None = None,  # np. "Jesteś parserem zgłoszeń helpdesku."
    ) -> LLMCompletion:
        """
        Description:
        Zapisuje wywołanie i odpowiada ze scenariusza. Bez sieci i bez czekania — korutyna jest
        asynchroniczna tylko po to, żeby mieć tę samą sygnaturę co prawdziwy dostawca.

        Example args:
            prompt="Zgłoszenie klienta:\\n\\nDrukarka nie drukuje…"
            system="Jesteś parserem zgłoszeń helpdesku."

        Example result:
            LLMCompletion(text="fake-llm-response", model="fake", prompt_tokens=6, …)

        Raises:
            LLMError: scenariusz odpowiedzi się skończył
        """
        started_at = time.perf_counter()

        self.calls.append(LLMCall(prompt=prompt, system=system))

        text       = self._take_response()
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        # Prawdziwy dostawca liczy też prompt systemowy, więc atrapa liczy obie części wejścia.
        billed_input = prompt if system is None else f"{system}\n{prompt}"

        completion = LLMCompletion(
            text              = text,
            model             = FAKE_MODEL_NAME,
            prompt_tokens     = self._count_tokens(billed_input),
            completion_tokens = self._count_tokens(text),
            latency_ms        = elapsed_ms,
        )

        self._log_call(prompt, completion)

        return completion

    async def complete_turn(
        self,
        system:   str,                       # np. "Jesteś asystentem wdrożeniowca helpdesku…"
        messages: Sequence[ChatMessage],     # np. [ChatMessage(role="user", content="…")]
        tools:    Sequence[ToolDefinition],  # np. [ToolDefinition(name="respond_search", …)]
    ) -> LLMTurn:
        """
        Description:
        Zapisuje wywołanie i oddaje kolejną turę ze scenariusza. Bez scenariusza odpowiada samym
        tekstem, bez narzędzi.

        Example args:
            system="Jesteś asystentem wdrożeniowca helpdesku…"
            messages=[ChatMessage(role="user", content="=== ZGŁOSZENIE ===\\nNie przychodzą…")]
            tools=[ToolDefinition(name="respond_search", …)]

        Example result:
            LLMTurn(message=ChatMessage(role="assistant", content="fake-llm-response"),
                    model="fake", latency_ms=0.01, usage=LLMUsage(calls=1, prompt_tokens=9, …))

        Raises:
            LLMError: scenariusz tur się skończył
        """
        started_at = time.perf_counter()

        self.turn_calls.append(LLMTurnCall(system=system, messages=messages, tools=tools))

        message    = self._take_turn()
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        # --- zużycie: wejściem jest prompt systemowy i cała rozmowa, wyjściem tekst i wywołania ---
        billed_input  = "\n".join([system, *(sent.content for sent in messages)])
        billed_output = " ".join([
            message.content,
            *(
                f"{call.name} {json.dumps(call.arguments, ensure_ascii=False)}"
                for call in message.tool_calls
            ),
        ])

        turn = LLMTurn(
            message    = message,
            model      = FAKE_MODEL_NAME,
            latency_ms = elapsed_ms,
            usage      = LLMUsage(
                calls             = 1,
                prompt_tokens     = self._count_tokens(billed_input),
                completion_tokens = self._count_tokens(billed_output),
            ),
        )

        self._log_turn(messages, turn)

        return turn

    def _take_response(self) -> str:
        """
        Description:
        Bierze kolejną odpowiedź ze scenariusza. Bez scenariusza — stała odpowiedź domyślna;
        scenariusz wyczerpany — błąd, bo powtórzenie ostatniej odpowiedzi przepuściłoby
        niespodziewane dodatkowe wywołanie.

        Example args:
            (brak)

        Example result:
            '{"problem": "Brak tonera"}'

        Raises:
            LLMError: wszystkie zaplanowane odpowiedzi zostały już oddane
        """
        if not self._responses:
            return DEFAULT_FAKE_RESPONSE

        if self._next_response >= len(self._responses):
            raise LLMError(
                f"FakeLLMClient: skończyły się zaplanowane odpowiedzi ({len(self._responses)})"
            )

        response = self._responses[self._next_response]
        self._next_response += 1

        return response

    def _take_turn(self) -> ChatMessage:
        """
        Description:
        Bierze kolejną turę ze scenariusza. Bez scenariusza — tura z samą odpowiedzią domyślną,
        bez narzędzi; scenariusz wyczerpany — błąd, jak w `_take_response()`.

        Example args:
            (brak)

        Example result:
            ChatMessage(role="assistant", tool_calls=[ToolCall(name="respond_search", …)])

        Raises:
            LLMError: wszystkie zaplanowane tury zostały już oddane
        """
        if not self._turns:
            return ChatMessage(role="assistant", content=DEFAULT_FAKE_RESPONSE)

        if self._next_turn >= len(self._turns):
            raise LLMError(f"FakeLLMClient: skończyły się zaplanowane tury ({len(self._turns)})")

        turn = self._turns[self._next_turn]
        self._next_turn += 1

        return turn

    @staticmethod
    def _count_tokens(
        text: str,  # np. "Drukarka nie drukuje"
    ) -> int:
        """
        Description:
        Przybliża liczbę tokenów liczbą słów. Atrapie to wystarcza: liczba ma być powtarzalna
        i niezerowa, żeby wpis w logu miał swój kształt — prawdziwy tokenizer ciągnąłby zależność
        dostawcy bez żadnego zysku.

        Example args:
            text="Drukarka nie drukuje"

        Example result:
            3
        """
        return len(text.split())
