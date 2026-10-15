"""
Description:
Przebieg spraw scenariuszy rozwiązania na żywym, płatnym modelu: `measure_solution_cases()`
przeprowadza sprawy sekcji grafu — każdą na jej narzędziach, czyli atrapach z kartami sprawy —
ocenia je i zgłasza do raportu zużycia i raportu ocen. Obok typ funkcji, którą oddaje fixture
`outcomes` testu na żywym modelu.

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture `outcomes`, która
  liczy sprawy grafu raz na plik (`remember_per_graph()`).
"""

import asyncio
from collections.abc import Callable

from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from tests._helpers.graphs import graph_module
from tests._helpers.live import LiveCase, LiveUsageReport, run_live_cases
from tests._helpers.scenarios.injections import source_keys
from tests._helpers.scenarios.solution.helper import (
    case_tools,
    judge_solution_case,
    solution_sections,
)
from tests._helpers.scenarios.solution.models.solution_outcome import SolutionOutcome
from tests._helpers.scenarios.solution.report import SolutionReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
SolutionOutcomesOf = Callable[[str], list[SolutionOutcome]]


def measure_solution_cases(
    name:            str,              # np. "suggest_solution"
    llm:             LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:      LiveUsageReport,  # raport zużycia przebiegu
    solution_report: SolutionReport,   # raport ocen spraw
) -> list[SolutionOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, każdą na jej narzędziach, ocenia je,
    zgłasza do obu raportów i oddaje oceny.

    Example args:
        name="suggest_solution"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        solution_report=SolutionReport()

    Example result:
        [SolutionOutcome(case=SolutionCase(case_id="r01", …), missing=(), …), …]

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = solution_sections()[name]
    graph   = graph_module(name)

    cases  = [LiveCase(text=case.text, tools=case_tools(case)) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[SolutionOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"rozwiązanie {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_solution_case(
            case    = case,
            output  = None if final is None else final.output,
            sources = () if final is None else (source_keys(final) or ()),
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        solution_report.record(name, outcome)
        judged.append(outcome)

    return judged
