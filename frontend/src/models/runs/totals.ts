/**
 * Description:
 * Liczniki przebiegu albo całej sesji — model frontu. Liczy je `runs/totals.ts`, pokazują belka
 * (`pages/panels/TopBar.tsx`) i nagłówki przebiegów (`runs/rows.ts`).
 *
 * Tokeny stoją w czterech rozłącznych klasach, jak w `UsageItem` z `api`; belka pokazuje je
 * parami: nowe (in/out) i cache (read/write).
 */

/** Liczniki jednego przebiegu albo całej sesji. */
export interface Totals {
    costUsd:          number;  // np. 0.069
    llmCalls:         number;  // np. 6
    inputTokens:      number;  // np. 1200 — świeże wejście, bez cache
    outputTokens:     number;  // np. 4100
    cacheReadTokens:  number;  // np. 108000
    cacheWriteTokens: number;  // np. 31000
    toolCalls:        number;  // np. 7
    turns:            number;  // np. 6 — kroki tur modelu
    runs:             number;  // np. 3
    durationMs:       number;  // np. 27400
}
