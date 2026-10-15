"""
Description:
Przebieg spraw scenariuszy wstrzyknięć na żywym, płatnym modelu: `measure_injection_cases()`
przeprowadza sprawy sekcji grafu — każde wejście idzie raz bez ataku, a każdy atak raz — ocenia je i
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
from tests._helpers.fake_tools import fake_agent_tools_with_tickets
from tests._helpers.graphs import graph_module
from tests._helpers.live import LiveCase, LiveUsageReport, default_rules, run_live_cases
from tests._helpers.scenarios.injections.helper import (
    injection_cases,
    injection_sections,
    judge_run,
    reached_model,
    source_keys,
)
from tests._helpers.scenarios.injections.models.injection_outcome import InjectionOutcome
from tests._helpers.scenarios.injections.report import InjectionReport

# Oceny spraw jednego grafu: najpierw kontrolne, potem ataki.
InjectionOutcomes = tuple[list[InjectionOutcome], list[InjectionOutcome]]


# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
InjectionOutcomesOf = Callable[[str], InjectionOutcomes]


def measure_injection_cases(
    name:             str,               # np. "suggest_handoff"
    llm:              LLMSettings,       # np. live_generation_llm(request.config)
    live_usage:       LiveUsageReport,   # raport zużycia przebiegu
    injection_report: InjectionReport,   # raport ocen spraw
) -> InjectionOutcomes:
    """
    Description:
    Przeprowadza sprawy jednego grafu na żywym modelu — każde wejście bez ataku i każdy atak —
    ocenia je, zgłasza do obu raportów i oddaje oceny: kontrolne i ataki osobno. Sekcja pod inną
    wersją reguł klienta niż zestaw domyślny kończy pomiar, zanim zawoła model.

    Example args:
        name="suggest_handoff"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        injection_report=InjectionReport()

    Example result:
        ([InjectionOutcome(label="kontrolna podpis", control=True, …), …],
         [InjectionOutcome(label="h01 polecenie wprost w komentarzu klienta", …), …])

    Raises:
        AssertionError: reguły klienta w innej wersji niż sekcja
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = injection_sections()[name]
    graph   = graph_module(name)
    cases   = injection_cases(section, default_rules(name, section.rules_version))

    live = [
        LiveCase(
            text  = case.text,
            rules = case.rules,
            tools = fake_agent_tools_with_tickets(case.cards, case.threads),
        )
        for case in cases
    ]
    finals = asyncio.run(run_live_cases(graph, llm, live))

    judged: list[InjectionOutcome] = []

    for case, final in zip(cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"wstrzyknięcie {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_run(
            label          = case.label,
            control        = case.control,
            markers        = case.markers,
            output         = None if final is None else final.output,
            sources        = None if final is None else source_keys(final),
            guarded_fields = section.guarded_fields,
            expected       = case.expected,
            retries        = MAX_RETRIES if final is None else final.respond_retries,
            delivered      = final is None or reached_model(final.messages, case.markers),
        )

        injection_report.record(name, outcome)
        judged.append(outcome)

    controls = [outcome for outcome in judged if outcome.control]
    attacks  = [outcome for outcome in judged if not outcome.control]

    measured = (controls, attacks)

    return measured
