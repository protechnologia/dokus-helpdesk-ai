"""
Description:
Przebieg spraw scenariuszy przekazania na żywym, płatnym modelu: `measure_handoff_cases()`
przeprowadza sprawy sekcji grafu, ocenia je i zgłasza do raportu zużycia i raportu ocen. Obok typ
funkcji, którą oddaje fixture `outcomes` testu na żywym modelu.

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
from tests._helpers.scenarios.handoff.helper import handoff_sections, judge_handoff_case
from tests._helpers.scenarios.handoff.models.handoff_outcome import HandoffOutcome
from tests._helpers.scenarios.handoff.report import HandoffReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
HandoffOutcomesOf = Callable[[str], list[HandoffOutcome]]


def measure_handoff_cases(
    name:           str,              # np. "suggest_handoff"
    llm:            LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:     LiveUsageReport,  # raport zużycia przebiegu
    handoff_report: HandoffReport,    # raport ocen spraw
) -> list[HandoffOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, ocenia je, zgłasza do obu raportów
    i oddaje oceny.

    Example args:
        name="suggest_handoff"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        handoff_report=HandoffReport()

    Example result:
        [HandoffOutcome(case=HandoffCase(case_id="h01", …), layout=(), lost=(), …), …]

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = handoff_sections()[name]
    graph   = graph_module(name)

    cases  = [LiveCase(text=case.text) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[HandoffOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"przekazanie {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_handoff_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        handoff_report.record(name, outcome)
        judged.append(outcome)

    return judged
