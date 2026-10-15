"""
Description:
Przebieg spraw scenariuszy „Popraw” na żywym, płatnym modelu: `measure_polish_cases()` przeprowadza
sprawy sekcji grafu — każda sprawa idzie z zasadami stylu z zestawu domyślnego — ocenia je i zgłasza
do raportu zużycia i raportu ocen. Obok typ funkcji, którą oddaje fixture `outcomes` testu na żywym
modelu.

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture `outcomes`, która
  liczy sprawy grafu raz na plik (`remember_per_graph()`).
"""

import asyncio
from collections.abc import Callable

from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from tests._helpers.graphs import graph_module
from tests._helpers.live import LiveCase, LiveUsageReport, default_rules, run_live_cases
from tests._helpers.scenarios.polish.helper import judge_polish_case, polish_sections
from tests._helpers.scenarios.polish.models.polish_outcome import PolishOutcome
from tests._helpers.scenarios.polish.report import PolishReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
PolishOutcomesOf = Callable[[str], list[PolishOutcome]]


def measure_polish_cases(
    name:          str,              # np. "polish"
    llm:           LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:    LiveUsageReport,  # raport zużycia przebiegu
    polish_report: PolishReport,     # raport ocen spraw
) -> list[PolishOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy grafu na żywym modelu, z zasadami stylu z zestawu domyślnego,
    ocenia je, zgłasza do obu raportów i oddaje oceny. Sekcja pod inną wersją zasad kończy
    pomiar, zanim zawoła model.

    Example args:
        name="polish"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        polish_report=PolishReport()

    Example result:
        [PolishOutcome(case=PolishCase(case_id="s01", …), colloquial=(), lost=(), …), …]

    Raises:
        AssertionError: zasady stylu w innej wersji niż sekcja
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = polish_sections()[name]
    graph   = graph_module(name)
    rules   = default_rules(name, section.rules_version)

    cases  = [LiveCase(text=case.text, rules=rules) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[PolishOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"popraw {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_polish_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        polish_report.record(name, outcome)
        judged.append(outcome)

    return judged
