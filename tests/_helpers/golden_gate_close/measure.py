"""
Description:
Przebieg zestawu bramki zamknięcia na żywym, płatnym modelu: `measure_gate_close_cases()`
składa wejście każdego wpisu z wątku korpusu uciętego na zamknięciu, przepuszcza zamknięcia przez
graf `gate_close` po kilka naraz, z regułami z zestawu domyślnego, ocenia je i zgłasza do raportu
zużycia i raportu bramki zamknięcia.

Kroki:

1. Reguły z zestawu domyślnego, po sprawdzeniu, że to wersja, pod którą oznaczano zestaw.
2. Wątek każdego wpisu, ucięty na zamknięciu; skrót musi zgadzać się z zapisanym przy wpisie.
3. Zamknięcia przez graf, najwyżej `CONCURRENCY` naraz, z czasem każdej sprawy.
4. Ocena i zgłoszenie do obu raportów.

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture `outcomes`.
- Kroki 1 i 2 kończą się błędem, zanim cokolwiek trafi do modelu: etykiety pod inne reguły albo
  pod inny tekst nic nie mierzą, a kosztowałyby jak zwykle.
- Anonimizator to atrapa z `run_live_graph()`, która oddaje tekst bez zmian: wątki z korpusu
  są już po anonimizacji, a jej czas dolicza raport.
"""

import asyncio
from collections.abc import Sequence

from app.agent_graphs import gate_close
from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from tests._helpers.golden_gate_close.constants import CONCURRENCY
from tests._helpers.golden_gate_close.helper import (
    closing_thread,
    golden_gate_close_rules_version,
    judge_gate_close_case,
    thread_digest,
)
from tests._helpers.golden_gate_close.models.gate_close_outcome import GateCloseOutcome
from tests._helpers.golden_gate_close.models.golden_gate_close_case import GoldenGateCloseCase
from tests._helpers.golden_gate_close.report import GateCloseReport
from tests._helpers.live import LiveCase, LiveUsageReport, default_rules, run_timed_live_cases


def measure_gate_close_cases(
    cases:      Sequence[GoldenGateCloseCase],  # np. golden_gate_close_cases()
    llm:        LLMSettings,                    # np. live_generation_llm(request.config)
    live_usage: LiveUsageReport,                # raport zużycia przebiegu
    report:     GateCloseReport,                # raport bramki zamknięcia
) -> list[GateCloseOutcome]:
    """
    Description:
    Przeprowadza podane zamknięcia przez bramkę zamknięcia na żywym modelu, ocenia je, zgłasza
    do obu raportów i oddaje oceny w kolejności wpisów.

    Example args:
        cases=golden_gate_close_cases()
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        report=GateCloseReport()

    Example result:
        [GateCloseOutcome(case=GoldenGateCloseCase(ticket_id="33605", …), answer="pass", …), …]

    Raises:
        AssertionError: reguły w innej wersji niż zestaw albo wątek niezgodny ze skrótem wpisu
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    # --- reguły i wejścia: sprawdzone, zanim cokolwiek trafi do modelu ---
    rules   = default_rules("gate_close", golden_gate_close_rules_version())
    threads = [closing_thread(case.ticket_id, case.comments_at_close) for case in cases]
    changed = [
        case.ticket_id
        for case, thread in zip(cases, threads, strict=True)
        if thread_digest(thread) != case.digest
    ]

    assert not changed, (
        f"wątki niezgodne ze skrótem przy wpisie (zmieniły się od oznaczania): {changed} — "
        f"przejrzyj etykiety tych wpisów, zanim zmierzysz na nich bramkę"
    )

    # --- zamknięcia przez graf, kilka naraz ---
    live = [LiveCase(text=thread, rules=rules) for thread in threads]
    runs = asyncio.run(run_timed_live_cases(gate_close, llm, live, CONCURRENCY))

    judged: list[GateCloseOutcome] = []

    for case, run in zip(cases, runs, strict=True):
        final = run.final

        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"bramka zamknięcia: {case.ticket_id}", final.usage, final.log, final.messages,
            )

        outcome = judge_gate_close_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
            seconds = run.seconds,
        )

        report.record(outcome)
        judged.append(outcome)

    return judged
