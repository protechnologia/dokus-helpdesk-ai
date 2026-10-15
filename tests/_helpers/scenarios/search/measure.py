"""
Description:
Przebieg spraw scenariuszy rozpoznania na żywym, płatnym modelu: `measure_search_cases()`
przeprowadza sprawy sekcji grafu — każdą na jej narzędziach, z prawdziwym kodem aplikacji
syntetycznej — ocenia je i zgłasza do raportu zużycia i raportu ocen. Obok typ funkcji, którą
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
from tests._helpers.scenarios.search.helper import case_tools, judge_search_case, search_sections
from tests._helpers.scenarios.search.models.search_outcome import SearchOutcome
from tests._helpers.scenarios.search.report import SearchReport

# Funkcja z fixture `outcomes`: z nazwy grafu robi oceny jego spraw.
SearchOutcomesOf = Callable[[str], list[SearchOutcome]]


def measure_search_cases(
    name:          str,              # np. "search"
    llm:           LLMSettings,      # np. live_generation_llm(request.config)
    live_usage:    LiveUsageReport,  # raport zużycia przebiegu
    search_report: SearchReport,     # raport ocen spraw
) -> list[SearchOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy sekcji grafu na żywym modelu, każdą na jej narzędziach
    (`case_tools()`), ocenia je, zgłasza do obu raportów i oddaje oceny w kolejności zestawu.
    Sprawa, której węzeł `respond` nie przyjął, nie oddaje stanu, więc jej zużycia w raporcie
    zużycia nie ma.

    Example args:
        name="search"
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        search_report=SearchReport()

    Example result:
        [SearchOutcome(case=SearchCase(case_id="k01", …), cause_files=("…/RejestrSzablonow.php",),
                       …), …]

    Raises:
        AssertionError: paczki syntetycznej nie zbudowano
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    section = search_sections()[name]
    graph   = graph_module(name)

    cases  = [LiveCase(text=case.text, tools=case_tools(case)) for case in section.cases]
    finals = asyncio.run(run_live_cases(graph, llm, cases))

    judged: list[SearchOutcome] = []

    for case, final in zip(section.cases, finals, strict=True):
        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"rozpoznanie {name}: {case.label}", final.usage, final.log, final.messages,
            )

        outcome = judge_search_case(
            case     = case,
            output   = None if final is None else final.output,
            messages = () if final is None else final.messages,
            retries  = MAX_RETRIES if final is None else final.respond_retries,
        )

        search_report.record(name, outcome)
        judged.append(outcome)

    return judged
