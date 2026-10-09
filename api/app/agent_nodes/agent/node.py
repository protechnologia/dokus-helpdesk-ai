"""
Description:
Węzeł `agent`: jedna tura modelu w pętli grafu. Wysyła modelowi prompt grafu, dotychczasową
rozmowę i narzędzia, a turę, którą model odpowiedział, dokleja do rozmowy w stanie grafu.

Przed — stan po anonimizacji, rozmowa jeszcze pusta:

    SearchState(
        input_text = "Od wczoraj nie przychodzą przesyłki z e-Doręczeń.",
        anonymized = AnonymizedText(text="Od wczoraj nie przychodzą przesyłki z e-Doręczeń."),
        messages   = [],
        iterations = 0,
    )

Po — zmiana stanu, którą zwraca pierwsza tura (tu na atrapie modelu, która liczy słowa zamiast
tokenów i nic nie kosztuje):

    {
        "messages":   [ChatMessage(role="user", content="Poniżej zgłoszenie, do którego szukasz…"),
                       ChatMessage(role="assistant",
                                   tool_calls=[ToolCall(call_id="call_1",
                                                        name="find_tickets_vector", …)])],
        "iterations": 1,
        "usage":      LLMUsage(calls=1, prompt_tokens=246, completion_tokens=13, cost_usd=0.0),
        "log":        [LogEntry(node="agent", message="tura 1: narzędzia: read_docs; 0,0000 USD")],
    }

Co się dzieje po drodze:

1. Pierwsza tura otwiera rozmowę: tura użytkownika powstaje z promptu grafu (`user_prompt(state)`,
   czyli wyłącznie z tekstu po anonimizacji) i zostaje w `messages`. Kolejne tury biorą rozmowę
   ze stanu — są w niej już tury modelu i wyniki narzędzi.
2. Model dostaje prompt systemowy, rozmowę i narzędzia przez `LLMClient.complete_turn()`.
3. Tura modelu trafia do `messages`, licznik tur rośnie o jeden, zużycie tej tury idzie do
   `usage`, a do `log` jeden wpis z nazwami wywołanych narzędzi.

O czym pamiętać przy zmianach:

- Węzeł nie ocenia tury. Dokąd idzie przebieg, rozstrzyga graf po tym, co model wywołał, i po
  limicie tur (`route_after_agent`); czy narzędzie jest dozwolone, sprawdza `run_tools`, a czy
  odpowiedź ma poprawny kształt — `respond`.
- Prompt systemowy i narzędzia są te same w każdej turze i w tej samej kolejności: początek
  żądania musi być identyczny co do znaku, żeby dostawca czytał go z cache promptu.
- Wiadomości wracają do modelu w całości, razem z `provider_items` tur modelu — klient dostawcy
  odsyła je w następnej turze bez zmian.
- Węzeł bywa wołany jeszcze raz po `respond`: gdy ten odeśle odpowiedź do poprawki, w rozmowie
  jest już jego komunikat, a model dostaje jedną turę więcej.
- Błędu modelu węzeł nie łapie: `LLMError` zatrzymuje przebieg, a trasa oddaje 503.
"""

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from app.agent_nodes.agent.base import AgentNodeBase
from app.engine_llm import ChatMessage, LLMClient, ToolDefinition


class AgentNode(AgentNodeBase):
    """
    Description:
    Węzeł właściwy `agent`: pyta model o kolejną turę rozmowy i zapisuje ją w stanie grafu.

    Do czego:
    Jedyny węzeł, który rozmawia z modelem. Graf podaje mu swój prompt i narzędzia, które model
    może widzieć, a klienta modelu — fabryka; węzeł jest więc ten sam w każdym grafie, a zmiana
    dostawcy go nie dotyka.

    Flow:
        1. Konstruktor przyjmuje klienta modelu, prompt systemowy, funkcję składającą turę
           użytkownika ze stanu i definicje narzędzi.
        2. `run()` otwiera rozmowę turą użytkownika (tylko w pierwszej turze), woła
           `complete_turn()` i oddaje zmianę stanu z `turn_update()`.
    """

    def __init__(
        self,
        llm:           LLMClient,                   # np. FakeLLMClient(turns=[…])
        system_prompt: str,                         # np. search.system_prompt()
        user_prompt:   Callable[[BaseModel], str],  # np. search.user_prompt
        tools:         Sequence[ToolDefinition],    # np. search.model_tools(tools, limits)
    ):
        """
        Description:
        Przyjmuje klienta modelu oraz prompt i narzędzia grafu, w którym węzeł pracuje.

        Example args:
            llm=FakeLLMClient(turns=[tool_call_turn("respond_search", {})])
            system_prompt="Jesteś asystentem wdrożeniowca helpdesku…"
            user_prompt=search.user_prompt
            tools=[ToolDefinition(name="find_tickets_vector", …),
                   ToolDefinition(name="respond_search", …)]

        Example result:
            AgentNode gotowy do wpięcia w graf `search`

        Raises:
            ValueError: brak narzędzi — model nie miałby czym odpowiedzieć
        """
        # Każdy graf kończy się wywołaniem `respond_<graf>`, więc co najmniej ono musi tu być.
        if not tools:
            raise ValueError("węzeł agent bez narzędzi — graf źle złożony")

        self._llm           = llm
        self._system_prompt = system_prompt
        self._user_prompt   = user_prompt
        self._tools         = list(tools)

    async def run(
        self,
        state: BaseModel,  # np. stan grafu po anonimizacji, z messages=[…], iterations=0
    ) -> dict[str, Any]:
        """
        Description:
        Wykonuje jedną turę modelu i dokleja ją do rozmowy.

        Example args:
            state=SearchState(input_text="…", anonymized=AnonymizedText(text="…"), iterations=0)

        Example result:
            {"messages": [ChatMessage(role="user", …), ChatMessage(role="assistant", …)],
             "iterations": 1, "usage": LLMUsage(calls=1, …),
             "log": [LogEntry(node="agent", message="tura 1: narzędzia: read_docs; 0,0041 USD")]}

        Raises:
            ValueError: stan jeszcze nie przeszedł anonimizacji (zgłasza `user_prompt` grafu)
            LLMError: model nie odpowiedział
        """
        # --- pierwsza tura otwiera rozmowę turą użytkownika; potem jest już w stanie ---
        opening: list[ChatMessage] = []

        if not state.messages:
            opening = [ChatMessage(role="user", content=self._user_prompt(state))]

        # --- tura modelu ---
        turn = await self._llm.complete_turn(
            system   = self._system_prompt,
            messages = [*state.messages, *opening],
            tools    = self._tools,
        )

        # --- zapis w stanie ---
        update = self.turn_update(
            state    = state,
            messages = [*opening, turn.message],
            usage    = turn.usage,
        )

        return update
