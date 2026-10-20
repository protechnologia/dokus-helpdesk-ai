/**
 * Description:
 * Próbki do testów frontu: zużycie tury, kroki przebiegu i przebieg. Dzięki nim plik testu to
 * same testy, a dane, na których stoją asercje, leżą w jednym miejscu.
 *
 * | próbka               | do czego                                                     |
 * |----------------------|--------------------------------------------------------------|
 * | `sampleUsage()`      | zużycie jednej tury modelu z podanym kosztem                 |
 * | `sampleStep()`       | krok przebiegu podanego węzła, z polami do nadpisania         |
 * | `sampleToolCall()`   | wywołanie narzędzia z wynikiem                               |
 * | `sampleRun()`        | przebieg z krokami: anonimizacja, tura, narzędzia, tura, odpowiedź |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Każda próbka powstaje od nowa przy wywołaniu, więc test, który ją zmieni, nie psuje innych.
 * - Dane są zmyślone; czasy kroków to zegar `api`, czasy przebiegu — zegar przeglądarki.
 */

import type { UsageItem } from "../../../frontend/src/models/api/common";
import type { StepItem, ToolCallItem } from "../../../frontend/src/models/api/step";
import type { Run } from "../../../frontend/src/models/runs/run";

// Początek pierwszego kroku przebiegu w próbkach, w zegarze `api`.
export const STEP_ORIGIN = "2026-10-19T12:03:14.000Z";

// Tekst zgłoszenia po anonimizacji, który niesie krok `anonymize` próbnego przebiegu.
export const ANONYMIZED_TEXT = "{IMIĘ} {NAZWISKO} z UG Zalesie zgłasza, że przesyłki nie przychodzą.";

/**
 * Description:
 * Zużycie jednej tury modelu: jedno wywołanie, tokeny w czterech klasach i podany koszt.
 *
 * Example args:
 *     costUsd=0.021
 *
 * Example result:
 *     { llm_calls: 1, prompt_tokens: 100, completion_tokens: 400, cache_write_tokens: 3000, cache_read_tokens: 9000, cost_usd: 0.021 }
 */
export function sampleUsage(
    costUsd: number,  // np. 0.021
): UsageItem {
    const usage = {
        llm_calls:          1,
        prompt_tokens:      100,
        completion_tokens:  400,
        cache_write_tokens: 3000,
        cache_read_tokens:  9000,
        cost_usd:           costUsd,
    };

    return usage;
}

/**
 * Description:
 * Wywołanie narzędzia z wynikiem, z polami do nadpisania.
 *
 * Example args:
 *     changes={ result: '{"error": "limit"}' }
 *
 * Example result:
 *     { call_id: "call_1", tool: "find_tickets_vector", arguments: { problem: "…" }, result: '{"error": "limit"}', … }
 */
export function sampleToolCall(
    changes: Partial<ToolCallItem> = {},  // np. { tool: "read_tickets_card" }
): ToolCallItem {
    const call = {
        call_id:     "call_1",
        tool:        "find_tickets_vector",
        arguments:   { problem: "Brak nowych przesyłek" },
        result:      '{"tickets":[{"ticket_id":"90001","score":0.71}]}',
        started_at:  "2026-10-19T12:03:16.000Z",
        duration_ms: 412,
        ...changes,
    };

    return call;
}

/**
 * Description:
 * Krok przebiegu podanego węzła: bez zużycia, bez zleconych narzędzi i bez wywołań, z polami
 * do nadpisania.
 *
 * Example args:
 *     node="agent"
 *     changes={ usage: sampleUsage(0.021), requested_tools: ["find_tickets_vector"] }
 *
 * Example result:
 *     { node: "agent", message: "agent", started_at: STEP_ORIGIN, duration_ms: 1000, usage: { … }, … }
 */
export function sampleStep(
    node:    string,                  // np. "agent"
    changes: Partial<StepItem> = {},  // np. { started_at: "2026-10-19T12:03:15.000Z" }
): StepItem {
    const step = {
        node,
        message:         node,
        started_at:      STEP_ORIGIN,
        duration_ms:     1000,
        usage:           null,
        requested_tools: [],
        tool_calls:      [],
        anonymized_text: null,
        ...changes,
    };

    return step;
}

/**
 * Description:
 * Przebieg zakończony wynikiem `search`: anonimizacja, tura z wyszukaniem, krok narzędzi z dwoma
 * wywołaniami, tura z odpowiedzią i odpowiedź; trwał 27,4 s w zegarze przeglądarki.
 *
 * Example args:
 *     changes={ finishedAt: null }
 *
 * Example result:
 *     Run(id=1, kind="search", steps=[anonymize, agent, run_tools, agent, respond], …)
 */
export function sampleRun(
    changes: Partial<Run> = {},  // np. { finishedAt: null, error: "503: …" }
): Run {
    const steps = [
        sampleStep("anonymize", { message: "zanonimizowano 412 zn.", anonymized_text: ANONYMIZED_TEXT }),
        sampleStep("agent", {
            started_at:      "2026-10-19T12:03:15.000Z",
            usage:           sampleUsage(0.021),
            requested_tools: ["find_tickets_vector", "find_docs_vector"],
        }),
        sampleStep("run_tools", {
            started_at: "2026-10-19T12:03:16.000Z",
            tool_calls: [
                sampleToolCall(),
                sampleToolCall({ call_id: "call_2", tool: "find_docs_vector", result: '{"error": "brak kolekcji"}' }),
            ],
        }),
        sampleStep("agent", {
            started_at:      "2026-10-19T12:03:17.000Z",
            usage:           sampleUsage(0.048),
            requested_tools: ["respond_search"],
        }),
        sampleStep("respond", { started_at: "2026-10-19T12:03:18.000Z", message: "odpowiedź przyjęta" }),
    ];

    const run = {
        id:          1,
        kind:        "search" as const,
        title:       "Rozpoznanie",
        ticketId:    "90101",
        draftInput:  null,
        startedAt:   1_000_000,
        lastEventAt: 1_020_000,
        finishedAt:  1_027_400,
        steps,
        outcome:     null,
        error:       null,
        ...changes,
    };

    return run;
}
