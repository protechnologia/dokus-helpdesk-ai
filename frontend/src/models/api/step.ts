/**
 * Description:
 * Krok przebiegu grafu ze strumienia trasy (zdarzenie `step`), przepisany z `StepItem`
 * i `ToolCallItem` w `api/app/entry_routers/models.py`.
 *
 * | pole              | w którym kroku                                       |
 * |-------------------|------------------------------------------------------|
 * | `usage`           | tylko w turze modelu (`agent`)                       |
 * | `requested_tools` | tylko w turze modelu: o co model poprosił            |
 * | `tool_calls`      | tylko w kroku `run_tools`: wykonane wywołania        |
 * | `anonymized_text` | tylko w kroku `anonymize`: tekst, który dostał model |
 *
 * Kto czyta: `runs/useRuns.ts` zbiera kroki przebiegu, `runs/rows.ts` robi z nich wiersze
 * konsoli i dialog szczegółów, `runs/totals.ts` liczy z nich koszt, tokeny i wywołania,
 * a `runs/answer.ts` bierze z kroku `anonymize` tekst po anonimizacji dla środkowego panelu.
 */

import type { UsageItem } from "./common";

/** Jedno wywołanie narzędzia w kroku `run_tools`: argumenty od modelu i wynik, który dostał. */
export interface ToolCallItem {
    call_id:     string;                   // np. "call_1"
    tool:        string;                   // np. "find_tickets_vector"
    arguments:   Record<string, unknown>;  // np. {"problem": "Brak przesyłek"}
    result:      string;                   // np. '{"tickets": [], "dropped_below_threshold": 3}'
    started_at:  string;                   // np. "2026-10-19T12:03:15.120000Z"
    duration_ms: number;                   // np. 84.2
}

/** Jeden krok przebiegu grafu (zdarzenie `step`). */
export interface StepItem {
    node:            string;            // np. "agent"
    message:         string;            // np. "tura 1: narzędzia: find_tickets_vector"
    started_at:      string;            // np. "2026-10-19T12:03:14.902000Z"
    duration_ms:     number;            // np. 2140.6
    usage:           UsageItem | null;
    requested_tools: string[];          // np. ["read_docs"]
    tool_calls:      ToolCallItem[];
    anonymized_text: string | null;     // np. "{IMIĘ} zgłasza brak przesyłek…"; null poza `anonymize`
}
