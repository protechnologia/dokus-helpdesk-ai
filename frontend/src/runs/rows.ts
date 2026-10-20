/**
 * Description:
 * Kroki przebiegu w kształcie konsoli: wiersz na krok, wiersz na każde wywołanie narzędzia,
 * na końcu wiersz kroku w toku; do każdego wiersza treść dialogu szczegółów. Tu stoi cała
 * wiedza konsoli o tym, co niesie który węzeł — komponenty tylko rysują wiersze.
 *
 * | krok strumienia | wiersz                         | dialog szczegółów                    |
 * |-----------------|--------------------------------|--------------------------------------|
 * | `anonymize`     | anonymize, wpis logu           | wpis logu, tekst po anonimizacji     |
 * | `agent`         | agent · tura N, koszt          | tokeny w czterech klasach, wywołania |
 * | `run_tools`     | ↳ narzędzie, „błąd” przy odmowie | zapytanie i odpowiedź dla modelu   |
 * | `respond`       | respond, wpis logu             | wpis logu                            |
 * | (w toku)        | to, co trwa, i czas od ostatniego kroku | brak                          |
 *
 * Przed — przebieg w toku po turze modelu, która poprosiła o odczyt kart:
 *
 *     steps: [anonymize, agent(requested_tools=["read_tickets_card"])], finishedAt: null
 *
 * Po — `runRows(run, now)`:
 *
 *     [ { label: "anonymize", … }, { label: "agent · tura 1", summary: "", … },
 *       { kind: "pending", label: "↳ read_tickets_card", summary: "w toku", … } ]
 *
 * O czym pamiętać przy zmianach:
 *
 * - Co trwa po turze modelu, mówi `requested_tools` z kroku tury, nie wpis logu: wpis to tekst
 *   dla człowieka. Tura bez wywołań albo z samym narzędziem odpowiedzi prowadzi do `respond`.
 * - Początek wiersza liczy się od początku pierwszego kroku, w zegarze `api`; czas wiersza
 *   w toku — od chwili, w której przeglądarka dostała ostatni krok, w jej zegarze.
 * - Wynik narzędzia to tekst, który dostał model; dialog pokazuje go z wcięciami, gdy jest
 *   JSON-em, a znak w znak, gdy nie jest.
 */

import type { ConsoleRow, RowKind } from "../models/runs/console";
import type { Run } from "../models/runs/run";
import type { StepItem, ToolCallItem } from "../models/api/step";
import { plural } from "../utils/count";
import { formatUsd } from "../utils/currency";
import { prettyJson } from "../utils/json";
import { formatClock, formatDuration } from "../utils/time";
import { runTotals } from "./totals";

// Narzędzie odpowiedzi grafu nazywa się `respond_<graf>`; po nim przebieg idzie do węzła `respond`.
const RESPOND_PREFIX = "respond_";

/**
 * Description:
 * Wiersze konsoli jednego przebiegu: po wierszu na krok (krok narzędzi rozpada się na wiersze
 * wywołań), a gdy przebieg trwa — na końcu wiersz tego, co trwa.
 *
 * Example args:
 *     run=Run(steps=[anonymize, agent], finishedAt=null)
 *     now=Date.now()
 *
 * Example result:
 *     [{ label: "anonymize", … }, { label: "agent · tura 1", … }, { kind: "pending", … }]
 */
export function runRows(
    run: Run,     // np. przebieg z useRuns()
    now: number,  // np. Date.now() — do czasu wiersza w toku
): ConsoleRow[] {
    const origin = run.steps.length > 0 ? Date.parse(run.steps[0].started_at) : 0;
    const rows: ConsoleRow[] = [];
    let turn = 0;

    for (const [index, step] of run.steps.entries()) {
        const key = `${run.id}-${index}`;

        // --- tura modelu: numer tury liczy się od jedynki ---
        if (step.node === "agent") {
            turn += 1;
            rows.push(turnRow(key, step, turn, origin));

            continue;
        }

        // --- krok narzędzi: wiersz na każde wywołanie, pod turą, która je zleciła ---
        if (step.node === "run_tools" && step.tool_calls.length > 0) {
            rows.push(...step.tool_calls.map((call) => toolRow(`${key}-${call.call_id}`, call, turn, origin)));

            continue;
        }

        rows.push(logRow(key, step, origin));
    }

    // --- przebieg trwa: wiersz tego, co trwa teraz ---
    if (run.finishedAt === null) {
        rows.push(pendingRow(run, now, origin));
    }

    return rows;
}

/**
 * Description:
 * Jedna linia o przebiegu: tury, wywołania narzędzi, koszt i czas, a w toku albo po błędzie —
 * dopisek o tym.
 *
 * Example args:
 *     run=Run(…)  // 6 tur, 7 wywołań narzędzi, 0,069 USD, 27,4 s
 *     now=Date.now()
 *
 * Example result:
 *     "6 tur · 7 narzędzi · 0,069 USD · 27,4 s"
 */
export function runSummary(
    run: Run,     // np. przebieg z useRuns()
    now: number,  // np. Date.now()
): string {
    const totals = runTotals(run, now);

    const parts = [
        plural(totals.turns, ["tura", "tury", "tur"]),
        plural(totals.toolCalls, ["narzędzie", "narzędzia", "narzędzi"]),
        formatUsd(totals.costUsd),
        formatDuration(totals.durationMs),
    ];

    // --- stan przebiegu, gdy nie jest zwykłym końcem ---
    if (run.finishedAt === null) {
        parts.push("w toku");
    } else if (run.error !== null) {
        parts.push("błąd");
    }

    return parts.join(" · ");
}

/**
 * Description:
 * Co trwa w przebiegu teraz, wnioskowane z ostatniego kroku: przed pierwszym krokiem
 * anonimizacja, po niej i po narzędziach kolejna tura modelu, po turze — narzędzia, o które
 * poprosił model, albo odpowiedź.
 *
 * Example args:
 *     steps=[anonymize, agent(requested_tools=["read_docs"])]
 *
 * Example result:
 *     "↳ read_docs"
 */
export function pendingLabel(
    steps: StepItem[],  // np. kroki przebiegu w toku
): string {
    const last  = steps.at(-1);
    const turns = steps.filter((step) => step.node === "agent").length;

    // --- przed pierwszym krokiem: anonimizacja to zawsze pierwszy węzeł ---
    if (last === undefined) {
        return "anonymize";
    }

    // --- po turze modelu: narzędzia wiedzy, jeśli o nie poprosił; inaczej odpowiedź ---
    if (last.node === "agent") {
        const tools = last.requested_tools.filter((name) => !name.startsWith(RESPOND_PREFIX));

        return tools.length > 0 ? `↳ ${tools.join(", ")}` : "respond";
    }

    // --- po anonimizacji, narzędziach albo odpowiedzi odesłanej do poprawki: kolejna tura ---
    return `agent · tura ${turns + 1}`;
}

/**
 * Description:
 * Wiersz tury modelu z kosztem tury, bez podsumowania — wywołania, o które poprosił model, stoją
 * w wierszach pod nią. Dialog pokazuje tokeny w czterech klasach i listę wywołań.
 *
 * Example args:
 *     key="3-1"
 *     step=StepItem(node="agent", usage={…}, requested_tools=["find_tickets_vector"])
 *     turn=1
 *     origin=Date.parse("2026-10-19T12:03:14.902Z")
 *
 * Example result:
 *     { kind: "turn", label: "agent · tura 1", summary: "", cost: "0,004 USD", … }
 */
function turnRow(
    key:    string,    // np. "3-1"
    step:   StepItem,  // krok węzła `agent`
    turn:   number,    // np. 1
    origin: number,    // ms: początek pierwszego kroku przebiegu
): ConsoleRow {
    const usage     = step.usage;
    const requested = step.requested_tools.length > 0 ? step.requested_tools.join(", ") : "sam tekst, bez wywołań";
    const tokens    = usage === null ? "brak danych o zużyciu" : [
        `świeże wejście   ${usage.prompt_tokens}`,
        `zapis do cache   ${usage.cache_write_tokens}`,
        `odczyt z cache   ${usage.cache_read_tokens}`,
        `wyjście          ${usage.completion_tokens}`,
    ].join("\n");

    const start    = formatClock(Date.parse(step.started_at) - origin);
    const cost     = usage === null ? "" : formatUsd(usage.cost_usd);
    const duration = formatDuration(step.duration_ms);

    const row = {
        key,
        kind:     "turn" as const,
        start,
        label:    `agent · tura ${turn}`,
        // Bez podsumowania: zlecone wywołania stoją wiersz niżej, a ich listę ma dialog.
        summary:  "",
        cost,
        duration,
        detail:   {
            title:    `Tura ${turn} · agent`,
            meta:     [`start ${start}`, duration, cost].filter(Boolean).join(" · "),
            sections: [
                { heading: "Tokeny", note: "", body: tokens },
                { heading: "Wywołania", note: "o co model poprosił w tej turze", body: requested },
            ],
        },
    };

    return row;
}

/**
 * Description:
 * Wiersz jednego wywołania narzędzia: czas wywołania, a w podsumowaniu „błąd", gdy model dostał
 * błąd zamiast wyniku — poza tym bez podsumowania, bo wynik pokazuje dialog po kliknięciu.
 * Dialog pokazuje zapytanie, odpowiedź i jej długość.
 *
 * Example args:
 *     key="3-2-call_1"
 *     call=ToolCallItem(tool="find_tickets_vector", arguments={…}, result="{…}", …)
 *     turn=1
 *     origin=Date.parse("2026-10-19T12:03:14.902Z")
 *
 * Example result:
 *     { kind: "tool", label: "↳ find_tickets_vector", summary: "", duration: "412 ms", … }
 */
function toolRow(
    key:    string,        // np. "3-2-call_1"
    call:   ToolCallItem,  // wywołanie z kroku `run_tools`
    turn:   number,        // np. 1 — tura, która je zleciła
    origin: number,        // ms: początek pierwszego kroku przebiegu
): ConsoleRow {
    const start    = formatClock(Date.parse(call.started_at) - origin);
    const duration = formatDuration(call.duration_ms);
    const summary  = isToolError(call.result) ? "błąd" : "";
    const size     = `${call.result.length} zn.`;

    const row = {
        key,
        kind:     "tool" as const,
        start,
        label:    `↳ ${call.tool}`,
        summary,
        cost:     "",
        duration,
        detail:   {
            title:    `${call.tool} · tura ${turn}`,
            meta:     [`start ${start}`, duration, size, summary].filter(Boolean).join(" · "),
            sections: [
                { heading: "Zapytanie", note: "argumenty od modelu", body: JSON.stringify(call.arguments, null, 2) },
                {
                    heading: "Odpowiedź",
                    note:    `to, co dostał model · ${call.result.length} zn.`,
                    body:    prettyJson(call.result),
                },
            ],
        },
    };

    return row;
}

/**
 * Description:
 * Wiersz kroku bez tury modelu i bez wywołań (anonimizacja, odpowiedź, krok narzędzi bez
 * wywołań): sam wpis logu.
 *
 * Example args:
 *     key="3-0"
 *     step=StepItem(node="anonymize", message="zanonimizowano 412 zn.", …)
 *     origin=Date.parse("2026-10-19T12:03:14.902Z")
 *
 * Example result:
 *     { kind: "anonymize", label: "anonymize", summary: "zanonimizowano 412 zn.", … }
 *     — w dialogu wpis logu i, przy anonimizacji, tekst, który dostał model
 */
function logRow(
    key:    string,    // np. "3-0"
    step:   StepItem,  // krok węzła innego niż `agent`
    origin: number,    // ms: początek pierwszego kroku przebiegu
): ConsoleRow {
    const start    = formatClock(Date.parse(step.started_at) - origin);
    const duration = formatDuration(step.duration_ms);

    // Własny wygląd mają anonimizacja i odpowiedź; inne węzły dostają wygląd ogólny.
    const kind: RowKind = step.node === "anonymize" || step.node === "respond" ? step.node : "other";

    // Wpis logu, a przy anonimizacji pod nim tekst, który dostał model.
    const sections = [{ heading: "Wpis logu", note: "", body: step.message || "(bez wpisu)" }];

    if (step.anonymized_text !== null) {
        sections.push({
            heading: "Tekst po anonimizacji",
            note:    `to, co dostał model · ${step.anonymized_text.length} zn.`,
            body:    step.anonymized_text,
        });
    }

    const row = {
        key,
        kind,
        start,
        label:    step.node,
        summary:  step.message,
        cost:     "",
        duration,
        detail:   {
            title:    step.node,
            meta:     `start ${start} · ${duration}`,
            sections,
        },
    };

    return row;
}

/**
 * Description:
 * Wiersz tego, co trwa teraz: zaczyna się tam, gdzie skończył się ostatni krok, a jego czas
 * liczy się od chwili, w której przeglądarka dostała ostatni krok (albo wysłała żądanie).
 *
 * Example args:
 *     run=Run(steps=[anonymize], lastEventAt=…, finishedAt=null)
 *     now=Date.now()
 *     origin=Date.parse("2026-10-19T12:03:14.902Z")
 *
 * Example result:
 *     { kind: "pending", label: "agent · tura 1", summary: "w toku", duration: "0,9 s", detail: null, … }
 */
function pendingRow(
    run:    Run,     // przebieg w toku
    now:    number,  // np. Date.now()
    origin: number,  // ms: początek pierwszego kroku przebiegu
): ConsoleRow {
    const last  = run.steps.at(-1);
    const start = last === undefined ? 0 : Date.parse(last.started_at) + last.duration_ms - origin;

    const row = {
        key:      `${run.id}-pending`,
        kind:     "pending" as const,
        start:    formatClock(start),
        label:    pendingLabel(run.steps),
        summary:  "w toku",
        cost:     "",
        duration: formatDuration(Math.max(0, now - run.lastEventAt)),
        detail:   null,
    };

    return row;
}

/**
 * Description:
 * Mówi, czy wynik narzędzia to błąd, który dostał model (`{"error": …}`), a nie wynik.
 *
 * Example args:
 *     result='{"error": "limit wywołań wyczerpany"}'
 *
 * Example result:
 *     true
 */
function isToolError(
    result: string,  // np. '{"tickets": []}'
): boolean {
    try {
        const parsed: unknown = JSON.parse(result);

        return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed) && "error" in parsed;
    } catch {
        return false;
    }
}
