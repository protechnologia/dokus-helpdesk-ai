"""
Description:
Przebieg zestawu bramki wysyłki na żywym, płatnym modelu: `measure_gate_reply_cases()` wycina
wiadomość każdego wpisu z wątku korpusu, przepuszcza wiadomości przez graf `gate_reply` po kilka
naraz, z regułami z zestawu domyślnego, ocenia je i zgłasza do raportu zużycia i raportu bramki
wysyłki.

Kroki:

1. Reguły z zestawu domyślnego, po sprawdzeniu, że to wersja, pod którą oznaczano zestaw.
2. Wiadomość każdego wpisu z korpusu; skrót musi zgadzać się z zapisanym przy wpisie.
3. Wiadomości przez graf, najwyżej `CONCURRENCY` naraz, z czasem każdej sprawy.
4. Ocena i zgłoszenie do obu raportów.

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture `outcomes`.
- Kroki 1 i 2 kończą się błędem, zanim cokolwiek trafi do modelu: etykiety pod inne reguły albo
  pod inny tekst nic nie mierzą, a kosztowałyby jak zwykle.
- Anonimizator to atrapa z `run_live_graph()`, która oddaje tekst bez zmian: wiadomości z korpusu
  są już po anonimizacji, a jej czas dolicza raport.
"""

import asyncio
from collections.abc import Sequence

from app.agent_graphs import gate_reply
from app.agent_nodes.respond import MAX_RETRIES
from app.config import LLMSettings
from tests._helpers.golden_gate_reply.constants import CONCURRENCY
from tests._helpers.golden_gate_reply.helper import (
    corpus_message,
    golden_gate_reply_rules_version,
    judge_gate_reply_case,
    message_digest,
)
from tests._helpers.golden_gate_reply.models.gate_reply_outcome import GateReplyOutcome
from tests._helpers.golden_gate_reply.models.golden_gate_reply_case import GoldenGateReplyCase
from tests._helpers.golden_gate_reply.report import GateReplyReport
from tests._helpers.live import LiveCase, LiveUsageReport, default_rules, run_timed_live_cases


def measure_gate_reply_cases(
    cases:      Sequence[GoldenGateReplyCase],  # np. golden_gate_reply_cases()
    llm:        LLMSettings,                    # np. live_generation_llm(request.config)
    live_usage: LiveUsageReport,                # raport zużycia przebiegu
    report:     GateReplyReport,                # raport bramki wysyłki
) -> list[GateReplyOutcome]:
    """
    Description:
    Przeprowadza podane wiadomości przez bramkę wysyłki na żywym modelu, ocenia je, zgłasza do
    obu raportów i oddaje oceny w kolejności wpisów.

    Example args:
        cases=golden_gate_reply_cases()
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        live_usage=LiveUsageReport()
        report=GateReplyReport()

    Example result:
        [GateReplyOutcome(case=GoldenGateReplyCase(ticket_id="23921", …), answer="block", …), …]

    Raises:
        AssertionError: reguły w innej wersji niż zestaw albo wiadomość niezgodna ze skrótem wpisu
        LLMError: dostawca odmówił albo nie odpowiedział w czasie
    """
    # --- reguły i wejścia: sprawdzone, zanim cokolwiek trafi do modelu ---
    rules    = default_rules("gate_reply", golden_gate_reply_rules_version())
    messages = [corpus_message(case.ticket_id, case.comment) for case in cases]
    changed  = [
        f"{case.ticket_id}/{case.comment}"
        for case, message in zip(cases, messages, strict=True)
        if message_digest(message) != case.digest
    ]

    assert not changed, (
        f"wiadomości niezgodne ze skrótem przy wpisie (zmieniły się od oznaczania): {changed} — "
        f"przejrzyj etykiety tych wpisów, zanim zmierzysz na nich bramkę"
    )

    # --- wiadomości przez graf, kilka naraz ---
    live = [LiveCase(text=message, rules=rules) for message in messages]
    runs = asyncio.run(run_timed_live_cases(gate_reply, llm, live, CONCURRENCY))

    judged: list[GateReplyOutcome] = []

    for case, run in zip(cases, runs, strict=True):
        final = run.final

        # --- sprawa z wynikiem: zużycie do raportu; odrzucona nie oddała stanu ---
        if final is not None:
            live_usage.record(
                f"bramka wysyłki: {case.ticket_id}/{case.comment}", final.usage, final.log,
                final.messages,
            )

        outcome = judge_gate_reply_case(
            case    = case,
            output  = None if final is None else final.output,
            retries = MAX_RETRIES if final is None else final.respond_retries,
            seconds = run.seconds,
        )

        report.record(outcome)
        judged.append(outcome)

    return judged
