"""
Description:
Sprawy testu okablowania grafów na żywym, płatnym modelu
(`tests/integration/api_agent_graphs/test_api_agent_graphs_live.py`): każda przeprowadza graf na
prawdziwym modelu, zgłasza zużycie i przebieg do raportu i oddaje stan końcowy.

| co                                        | sprawa                                           |
|-------------------------------------------|--------------------------------------------------|
| `measure_example_case()`                  | stan przykładowy grafu, atrapy narzędzi          |
| `measure_solution_without_material()`     | `suggest_solution`, narzędzia nic nie znajdują   |
| `measure_solution_with_message_in_code()` | `suggest_solution`, komunikat tylko w kodzie     |

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture'y, które liczą sprawę raz
  na plik (`remember_per_graph()` albo fixture o zasięgu modułu).
- Sprawa zakończona błędem nie oddaje stanu, więc jej zużycia w raporcie nie ma.
"""

import asyncio
from collections.abc import Callable

from pydantic import BaseModel

from app.agent_graphs import suggest_solution
from app.config import LLMSettings
from tests._helpers.fake_tools import (
    fake_agent_tools,
    fake_agent_tools_with_code_only,
    fake_agent_tools_without_material,
)
from tests._helpers.graphs import graph_module
from tests._helpers.live.constants import TICKET_WITH_MESSAGE
from tests._helpers.live.helper import run_live_graph
from tests._helpers.live.report import LiveUsageReport

# Funkcja z fixture `live_run`: z nazwy grafu robi stan końcowy jego sprawy przykładowej.
LiveRunOf = Callable[[str], BaseModel]


def measure_example_case(
    name:       str,              # np. "search"
    llm:        LLMSettings,      # np. live_generation_llm(request.config)
    live_usage: LiveUsageReport,  # raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Przeprowadza sprawę przykładową grafu na żywym modelu, na atrapach wszystkich narzędzi,
    zgłasza jej zużycie i przebieg do raportu i oddaje stan końcowy.

    Example args:
        name="search"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()

    Example result:
        SearchState(sources=[…], iterations=4, …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział albo odpowiedź nie dała się przyjąć
    """
    final = asyncio.run(run_live_graph(graph_module(name), llm, fake_agent_tools()))

    live_usage.record(f"graf {name}", final.usage, final.log, final.messages)

    return final


def measure_solution_without_material(
    llm:        LLMSettings,      # np. live_generation_llm(request.config)
    live_usage: LiveUsageReport,  # raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Przeprowadza sprawę `suggest_solution` na żywym modelu, na narzędziach, które nic nie
    znajdują (`fake_agent_tools_without_material()`), zgłasza ją do raportu i oddaje stan
    końcowy.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()

    Example result:
        SuggestSolutionState(sources=[], output=ProposalNotes(internal_notes="Szukałem…"), …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział albo odpowiedź nie dała się przyjąć
    """
    tools = fake_agent_tools_without_material()
    final = asyncio.run(run_live_graph(suggest_solution, llm, tools))

    live_usage.record(
        "graf suggest_solution bez materiału", final.usage, final.log, final.messages,
    )

    return final


def measure_solution_with_message_in_code(
    llm:        LLMSettings,      # np. live_generation_llm(request.config)
    live_usage: LiveUsageReport,  # raport zużycia przebiegu
) -> BaseModel:
    """
    Description:
    Przeprowadza sprawę `suggest_solution` na żywym modelu, ze zgłoszeniem z komunikatem z ekranu
    (`TICKET_WITH_MESSAGE`) i materiałem tylko w kodzie aplikacji
    (`fake_agent_tools_with_code_only()`): zgłoszenia i instrukcje nic nie znajdują. Zgłasza ją
    do raportu i oddaje stan końcowy.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()

    Example result:
        SuggestSolutionState(sources=[SourceRef(source="code", …)], output=Proposal(…), …)

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział albo odpowiedź nie dała się przyjąć
    """
    tools = fake_agent_tools_with_code_only()
    final = asyncio.run(run_live_graph(suggest_solution, llm, tools, TICKET_WITH_MESSAGE))

    live_usage.record(
        "graf suggest_solution: komunikat tylko w kodzie", final.usage, final.log, final.messages,
    )

    return final
