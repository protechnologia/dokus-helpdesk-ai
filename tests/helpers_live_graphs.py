"""
Description:
Uruchomienie grafu na żywym, płatnym modelu w testach `llm_live`: graf złożony z węzłów
właściwych tą samą funkcją co w fabryce grafów, z atrapą anonimizatora i podanymi narzędziami.
Korzystają z niego test okablowania grafów (`tests/integration/api_agent_graphs/`) i scenariusze
ewaluacyjne (`tests/evaluation/`).

O czym pamiętać przy zmianach:

- Konfigurację modelu podaje wołający, wziętą przez `live_generation_llm()` z `tests/conftest.py`.
  Ta funkcja odmawia, gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa, więc
  tu jej się nie omija.
- Anonimizator to atrapa, bo zgłoszenia w tych testach są zmyślone; atrapa oddaje tekst bez zmian.
- Limity wywołań narzędzi i limit tur pochodzą z konfiguracji, tak jak w fabryce grafów.
"""

from collections.abc import Sequence
from types import ModuleType

from pydantic import BaseModel

from app.agent_graphs import run_graph
from app.agent_graphs.factory import build_real_graph
from app.agent_tools import AgentTool
from app.config import LLMSettings, Settings
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import get_llm_client


async def run_live_graph(
    graph:      ModuleType,           # np. <module app.agent_graphs.search>
    llm:        LLMSettings,          # np. live_generation_llm(request.config)
    tools:      Sequence[AgentTool],  # np. fake_agent_tools()
    input_text: str | None = None,    # np. "ZGŁOSZENIE 90101…"; None to przykładowe wejście grafu
) -> BaseModel:
    """
    Description:
    Składa graf tą samą funkcją, której używa fabryka grafów (`build_real_graph()`) — z limitami
    wywołań i limitem tur z konfiguracji — i przepuszcza przez niego wejście na prawdziwym
    modelu: przykładowy stan grafu (`example_state()`) albo ten stan z `input_text` podmienionym
    na podany. Reszta stanu, na przykład reguły klienta, zostaje jak w przykładzie.

    Example args:
        graph=<module app.agent_graphs.search>
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)
        tools=fake_agent_tools()
        input_text=None

    Example result:
        SearchState(sources=[SourceRef(item_id="90001", …), …], iterations=4,
                    usage=LLMUsage(calls=4, cost_usd=0.021, …), …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział w czasie albo oddał turę nie do użycia;
            także `RespondError`, gdy model mimo poprawki nie oddał poprawnej odpowiedzi
    """
    settings = Settings()

    compiled = build_real_graph(
        graph          = graph,
        llm            = get_llm_client(llm),
        anonymizer     = FakeAnonymizer(),
        tools          = tools,
        limits         = settings.tool_call_limits(),
        max_iterations = settings.agent_max_iterations,
    )

    state = graph.example_state()

    # --- własne wejście zamiast przykładowego: reszta stanu zostaje jak w przykładzie ---
    if input_text is not None:
        state = state.model_copy(update={"input_text": input_text})

    return await run_graph(compiled, state)
