/**
 * Description:
 * Liczniki przebiegów: koszt, wywołania modelu, tokeny w czterech klasach, wywołania narzędzi,
 * tury i czas — dla jednego przebiegu (nagłówek w konsoli i w środkowym panelu) i dla całej
 * sesji (belka).
 *
 * Przed — przebieg z dwiema turami modelu i krokiem narzędzi z dwoma wywołaniami:
 *
 *     steps: [anonymize, agent (usage 0,021 USD), run_tools (2 wywołania), agent (0,048 USD), respond]
 *
 * Po — `runTotals(run, now)`:
 *
 *     { costUsd: 0.069, llmCalls: 2, inputTokens: 200, outputTokens: 800, cacheReadTokens: 18000,
 *       cacheWriteTokens: 6000, toolCalls: 2, turns: 2, runs: 1, durationMs: 27400 }
 *
 * Kto czyta: `pages/panels/TopBar.tsx` (liczniki sesji z `sessionTotals()`) i `runs/rows.ts`
 * (nagłówek przebiegu z `runTotals()`).
 *
 * O czym pamiętać przy zmianach:
 *
 * - Zużycie liczy się z kroków tur modelu, nie z wyniku: przebieg zakończony błędem też
 *   kosztował, a wyniku nie ma.
 * - Tokeny stoją w czterech rozłącznych klasach, jak w `api`: świeże wejście, wyjście, odczyt
 *   i zapis cache. Belka pokazuje je parami: nowe (in/out) i cache (read/write).
 * - Przebieg w toku liczy czas do `now`, więc belka rośnie na żywo.
 */

import type { UsageItem } from "../models/api/common";
import type { Run } from "../models/runs/run";
import type { Totals } from "../models/runs/totals";

// Liczniki bez żadnego przebiegu: początek sumy sesji.
const NO_TOTALS: Totals = {
    costUsd:          0,
    llmCalls:         0,
    inputTokens:      0,
    outputTokens:     0,
    cacheReadTokens:  0,
    cacheWriteTokens: 0,
    toolCalls:        0,
    turns:            0,
    runs:             0,
    durationMs:       0,
};

/**
 * Description:
 * Liczniki jednego przebiegu, z jego kroków i czasu po stronie przeglądarki.
 *
 * Example args:
 *     run=Run(steps=[…], startedAt=…, finishedAt=…)
 *     now=Date.now()
 *
 * Example result:
 *     { costUsd: 0.069, llmCalls: 2, inputTokens: 200, outputTokens: 800, …, durationMs: 27400 }
 */
export function runTotals(
    run: Run,     // np. przebieg z useRuns()
    now: number,  // np. Date.now() — koniec przebiegu w toku
): Totals {
    const usages = run.steps
        .map((step) => step.usage)
        .filter((usage): usage is UsageItem => usage !== null);

    // Suma jednego pola zużycia po wszystkich turach przebiegu.
    const sum = (field: keyof UsageItem) => usages.reduce((total, usage) => total + usage[field], 0);

    const totals = {
        costUsd:          sum("cost_usd"),
        llmCalls:         sum("llm_calls"),
        inputTokens:      sum("prompt_tokens"),
        outputTokens:     sum("completion_tokens"),
        cacheReadTokens:  sum("cache_read_tokens"),
        cacheWriteTokens: sum("cache_write_tokens"),
        toolCalls:        run.steps.reduce((total, step) => total + step.tool_calls.length, 0),
        turns:            run.steps.filter((step) => step.node === "agent").length,
        runs:             1,
        durationMs:       (run.finishedAt ?? now) - run.startedAt,
    };

    return totals;
}

/**
 * Description:
 * Liczniki całej sesji: suma liczników przebiegów, pole po polu; bez przebiegów same zera.
 *
 * Example args:
 *     runs=[Run(…), Run(…), Run(…)]
 *     now=Date.now()
 *
 * Example result:
 *     { costUsd: 0.1, llmCalls: 11, inputTokens: 1200, …, toolCalls: 16, turns: 11, runs: 3, durationMs: 56500 }
 */
export function sessionTotals(
    runs: Run[],   // np. przebiegi z useRuns()
    now:  number,  // np. Date.now()
): Totals {
    const fields = Object.keys(NO_TOTALS) as (keyof Totals)[];

    const totals = runs
        .map((run) => runTotals(run, now))
        .reduce((total, one) => {
            const next = { ...total };

            fields.forEach((field) => { next[field] = total[field] + one[field]; });

            return next;
        }, NO_TOTALS);

    return totals;
}
