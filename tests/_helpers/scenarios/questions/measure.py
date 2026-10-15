"""
Description:
Przebieg spraw scenariuszy „pytań już nie trzeba” na żywym, płatnym modelu:
`measure_questions_cases()` przeprowadza sprawy sekcji grafu — każda sprawa idzie na atrapach
wszystkich narzędzi — ocenia je i zgłasza do raportu zużycia i raportu ocen. Obok typ funkcji, którą
oddaje fixture `outcomes` testu na żywym modelu.

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
from tests._helpers.scenarios.questions.helper import judge_questions_case, questions_sections
from tests._helpers.scenarios.questions.models.questions_outcome import QuestionsOutcome
from tests._helpers.scenarios.questions.report import QuestionsReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
QuestionsOutcomesOf = Callable[[str], list[QuestionsOutcome]]


def measure_questions_cases(
    name:             str,              # np. "suggest_questions"
    llm:              LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:       LiveUsageReport,  # raport zużycia przebiegu
    questions_report: QuestionsReport,  # raport ocen spraw
) -> list[QuestionsOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, na atrapach wszystkich narzędzi, ocenia
    je, zgłasza do obu raportów i oddaje oceny.

    Example args:
        name="suggest_questions"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        questions_report=QuestionsReport()

    Example result:
        [QuestionsOutcome(case=QuestionsCase(case_id="w01", …), asked=False, …), …]

    Raises:
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = questions_sections()[name]
    graph   = graph_module(name)

    cases  = [LiveCase(text=case.text) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[QuestionsOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"pytania {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_questions_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        questions_report.record(name, outcome)
        judged.append(outcome)

    return judged
