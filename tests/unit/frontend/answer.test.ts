/**
 * Description:
 * Testy tego, co środkowy panel bierze z przebiegu (`frontend/src/runs/answer.ts`): tekst dla
 * klienta, tekst po anonimizacji i źródła.
 */

import { describe, expect, test } from "vitest";

import { anonymizedTextOf, clientTextOf, sourcesOf } from "../../../frontend/src/runs/answer";
import type { SuggestResponse } from "../../../frontend/src/models/api/suggest";
import { ANONYMIZED_TEXT, sampleRun } from "./samples";

describe("clientTextOf", () => {
    /**
     * Sprawdza, czy tekstem dla klienta jest propozycja odpowiedzi, wynik „Popraw" i szkic
     * sprawdzony bramką wysyłki.
     *
     * Wyłapuje bramkę wysyłki, po której szkic znikałby z zakładki „Dla klienta" — człowiek
     * straciłby tekst, który właśnie sprawdzał — i propozycję, która nie trafia do szkicu.
     */
    test("takes the proposal, the polished text and the checked draft", () => {
        const proposal = sampleRun({
            kind:    "suggest",
            outcome: { kind: "suggest", result: { text: "Dzień dobry, …" } as SuggestResponse },
        });
        const polished = sampleRun({ kind: "polish", outcome: { kind: "polish", result: { text: "Szanowni Państwo, …" } as never } });
        const checked  = sampleRun({
            kind:       "gate_reply",
            draftInput: "Prosimy o hasło",
            outcome:    { kind: "gate_reply", result: {} as never },
        });

        expect(clientTextOf(proposal)).toBe("Dzień dobry, …");
        expect(clientTextOf(polished)).toBe("Szanowni Państwo, …");
        expect(clientTextOf(checked)).toBe("Prosimy o hasło");
    });

    /**
     * Sprawdza, czy rozpoznanie, wariant bez treści dla klienta, przebieg w toku i przebieg
     * zakończony błędem nie mają tekstu dla klienta.
     *
     * Wyłapuje stary tekst w zakładce „Dla klienta" po rozpoznaniu albo karcie: wyglądałby jak
     * wynik przebiegu, który tekstu nie dał.
     */
    test("gives no text when the run has none", () => {
        const search  = sampleRun({ outcome: { kind: "search", result: {} as never } });
        const noText  = sampleRun({
            kind:    "suggest",
            outcome: { kind: "suggest", result: { text: null } as SuggestResponse },
        });
        const running = sampleRun({ finishedAt: null });
        const failed  = sampleRun({ error: "503: anonimizator nie odpowiedział" });

        expect([search, noText, running, failed].map(clientTextOf)).toEqual([null, null, null, null]);
    });
});

describe("anonymizedTextOf", () => {
    /**
     * Sprawdza, czy tekst po anonimizacji pochodzi z kroku `anonymize`, a przebieg bez tego
     * kroku (padł przed nim albo krok jeszcze nie przyszedł) nie ma tekstu.
     *
     * Wyłapuje tekst brany z innego kroku i błąd przy przebiegu bez kroków — zakładka „Po
     * anonimizacji" i ramka błędu wywracałyby panel.
     */
    test("reads the anonymize step", () => {
        expect(anonymizedTextOf(sampleRun())).toBe(ANONYMIZED_TEXT);
        expect(anonymizedTextOf(sampleRun({ steps: [] }))).toBeNull();
    });
});

describe("sourcesOf", () => {
    /**
     * Sprawdza, czy źródła mają tylko rozpoznanie i propozycja odpowiedzi, a przebieg w toku
     * i bramka — pustą listę.
     *
     * Wyłapuje źródła wzięte z wyniku, który ich nie ma (błąd przy bramce), i zgubione źródła
     * rozpoznania.
     */
    test("takes sources from search and suggest only", () => {
        const source = { source: "tickets", item_id: "90001", title: "Brak przesyłek", date: "2026-03-14" };
        const search = sampleRun({ outcome: { kind: "search", result: { sources: [source] } as never } });
        const gate   = sampleRun({ kind: "gate_close", outcome: { kind: "gate_close", result: {} as never } });

        expect(sourcesOf(search)).toEqual([source]);
        expect(sourcesOf(gate)).toEqual([]);
        expect(sourcesOf(sampleRun({ finishedAt: null }))).toEqual([]);
    });
});
