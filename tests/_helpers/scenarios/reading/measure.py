"""
Description:
Przebieg spraw scenariuszy czytania na żywym, płatnym modelu: `measure_reading_cases()`
przeprowadza sprawy sekcji grafu — każda sprawa idzie na atrapach wszystkich narzędzi — ocenia je
i zgłasza do raportu zużycia i raportu ocen. Obok typ funkcji, którą oddaje fixture `outcomes`
testu na żywym modelu.

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
from tests._helpers.scenarios.reading.helper import judge_reading_case, reading_sections
from tests._helpers.scenarios.reading.models.reading_outcome import ReadingOutcome
from tests._helpers.scenarios.reading.report import ReadingReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
ReadingOutcomesOf = Callable[[str], list[ReadingOutcome]]


def measure_reading_cases(
    name:           str,              # np. "search"
    llm:            LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:     LiveUsageReport,  # raport zużycia przebiegu
    reading_report: ReadingReport,    # raport ocen spraw
) -> list[ReadingOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, na atrapach wszystkich narzędzi, ocenia
    je, zgłasza do obu raportów i oddaje oceny.

    Example args:
        name="search"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        reading_report=ReadingReport()

    Example result:
        [ReadingOutcome(case=ReadingCase(case_id="c01", …), unread=(), …), …]

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = reading_sections()[name]
    graph   = graph_module(name)

    cases  = [LiveCase(text=case.text) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[ReadingOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"czytanie {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_reading_case(
            case     = case,
            output   = None if final is None else final.output,
            sources  = () if final is None else (source_keys(final) or ()),
            messages = () if final is None else final.messages,
            retries  = MAX_RETRIES if final is None else final.respond_retries,
        )

        reading_report.record(name, outcome)
        judged.append(outcome)

    return judged
