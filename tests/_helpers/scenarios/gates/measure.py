"""
Description:
Przebieg spraw scenariuszy bramek na żywym, płatnym modelu: `measure_gate_cases()` przeprowadza
sprawy sekcji grafu — każda sprawa bramki idzie z regułami z zestawu domyślnego — ocenia je i
zgłasza do raportu zużycia i raportu ocen. Obok typ funkcji, którą oddaje fixture `outcomes` testu
na żywym modelu.

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
from tests._helpers.scenarios.gates.helper import gate_sections, judge_gate_case
from tests._helpers.scenarios.gates.models.gate_outcome import GateOutcome
from tests._helpers.scenarios.gates.report import GateReport

# Funkcja z fixture `outcomes`: z nazwy bramki robi oceny jej spraw.
GateOutcomesOf = Callable[[str], list[GateOutcome]]


def measure_gate_cases(
    name:        str,              # np. "gate_reply"
    llm:         LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:  LiveUsageReport,  # raport zużycia przebiegu
    gate_report: GateReport,       # raport ocen spraw
) -> list[GateOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy jednej bramki na żywym modelu, z regułami z zestawu domyślnego,
    ocenia je, zgłasza do obu raportów i oddaje oceny. Sekcja pod inną wersją reguł kończy
    pomiar, zanim zawoła model.

    Example args:
        name="gate_reply"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        gate_report=GateReport()

    Example result:
        [GateOutcome(case=GateCase(case_id="g01", …), answer="block", …), …]

    Raises:
        AssertionError: reguły w innej wersji niż sekcja
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = gate_sections()[name]
    graph   = graph_module(name)
    rules   = default_rules(name, section.rules_version)

    cases  = [LiveCase(text=case.text, rules=rules) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[GateOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"bramka {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_gate_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
        )

        gate_report.record(name, outcome)
        judged.append(outcome)

    return judged
