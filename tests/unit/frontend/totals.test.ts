/**
 * Description:
 * Testy liczników (`frontend/src/runs/totals.ts`): czy belka i nagłówki przebiegów pokazują koszt,
 * wywołania, tokeny i czas zgodne z krokami przebiegów.
 */

import { describe, expect, test } from "vitest";

import { runTotals, sessionTotals } from "../../../frontend/src/runs/totals";
import { sampleRun } from "./samples";

describe("runTotals", () => {
    /**
     * Sprawdza, czy liczniki przebiegu sumują zużycie obu tur modelu (koszt 0,069 USD,
     * 2 wywołania modelu, każdą z czterech klas tokenów osobno), liczą wywołania narzędzi
     * z kroku narzędzi i biorą czas z zegara przeglądarki.
     *
     * Wyłapuje koszt wzięty z jednej tury zamiast z obu, pomylone klasy tokenów (odczyt cache
     * pokazany jako zapis albo jako nowe wejście) i czas liczony z kroków `api` zamiast
     * z czekania człowieka.
     */
    test("sums model turns and tool calls of one run", () => {
        const totals = runTotals(sampleRun(), 2_000_000);

        expect(totals.costUsd).toBeCloseTo(0.069, 6);
        expect(totals).toMatchObject({
            llmCalls:         2,
            inputTokens:      2 * 100,
            outputTokens:     2 * 400,
            cacheReadTokens:  2 * 9000,
            cacheWriteTokens: 2 * 3000,
            toolCalls:        2,
            turns:            2,
            runs:             1,
            durationMs:       27_400,
        });
    });

    /**
     * Sprawdza, czy przebieg w toku liczy czas do podanej chwili, a przebieg zakończony błędem —
     * koszt z kroków, choć wyniku nie ma.
     *
     * Wyłapuje belkę, która stoi w miejscu w trakcie przebiegu, i przebieg z błędem pokazany za
     * darmo, choć model go policzył.
     */
    test("counts a running run up to now and a failed run from its steps", () => {
        const running = runTotals(sampleRun({ finishedAt: null }), 1_003_000);
        const failed  = runTotals(sampleRun({ error: "503: …" }), 2_000_000);

        expect(running.durationMs).toBe(3_000);
        expect(failed.costUsd).toBeCloseTo(0.069, 6);
    });
});

describe("sessionTotals", () => {
    /**
     * Sprawdza, czy liczniki sesji to suma liczników przebiegów, a bez przebiegów same zera.
     *
     * Wyłapuje belkę, która pokazuje tylko ostatni przebieg, i błąd przy pustej sesji tuż po
     * otwarciu strony.
     */
    test("adds runs up and starts from zero", () => {
        const totals = sessionTotals([sampleRun(), sampleRun({ id: 2 })], 2_000_000);

        expect(totals).toMatchObject({ llmCalls: 4, cacheReadTokens: 4 * 9000, toolCalls: 4, runs: 2, durationMs: 54_800 });
        expect(Object.values(sessionTotals([], 0)).every((value) => value === 0)).toBe(true);
    });
});
