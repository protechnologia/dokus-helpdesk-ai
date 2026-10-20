/**
 * Description:
 * Testy wierszy konsoli (`frontend/src/runs/rows.ts`): czy kroki przebiegu stają się właściwymi
 * wierszami, czy wiersz w toku mówi, co naprawdę trwa, i czy nagłówek przebiegu liczy dobrze.
 */

import { describe, expect, test } from "vitest";

import { pendingLabel, runRows, runSummary } from "../../../frontend/src/runs/rows";
import { ANONYMIZED_TEXT, sampleRun, sampleStep, sampleToolCall, sampleUsage } from "./samples";

describe("runRows", () => {
    /**
     * Sprawdza, czy przebieg z anonimizacją, turą, krokiem z dwoma wywołaniami, drugą turą
     * i odpowiedzią daje sześć wierszy w tej kolejności, z wywołaniami narzędzi pod turą, która
     * je zleciła, i bez wiersza w toku po zakończeniu.
     *
     * Wyłapuje krok narzędzi pokazany jako jeden wiersz zamiast wiersza na wywołanie, zgubiony
     * krok albo wiersz „w toku" przy przebiegu, który już się skończył.
     */
    test("gives a row per step and a row per tool call", () => {
        const rows = runRows(sampleRun(), 2_000_000);

        expect(rows.map((row) => [row.kind, row.label])).toEqual([
            ["anonymize", "anonymize"],
            ["turn", "agent · tura 1"],
            ["tool", "↳ find_tickets_vector"],
            ["tool", "↳ find_docs_vector"],
            ["turn", "agent · tura 2"],
            ["respond", "respond"],
        ]);
    });

    /**
     * Sprawdza, czy początek wiersza liczy się od pierwszego kroku przebiegu w zegarze `api`
     * (tura 1 sekundę po anonimizacji to „00:01.0"), a koszt stoi tylko przy turze modelu.
     *
     * Wyłapuje początki liczone od zegara przeglądarki (rozjazd zegarów daje bzdurne godziny)
     * i koszt przypisany wierszowi narzędzia albo anonimizacji.
     */
    test("starts rows from the first step and prices only model turns", () => {
        const rows = runRows(sampleRun(), 2_000_000);

        expect(rows.map((row) => row.start)).toEqual(["00:00.0", "00:01.0", "00:02.0", "00:02.0", "00:03.0", "00:04.0"]);
        expect(rows.map((row) => row.cost)).toEqual(["", "0,021 USD", "", "", "0,048 USD", ""]);
    });

    /**
     * Sprawdza, czy wywołanie narzędzia, które dostało od `api` błąd `{"error": …}`, ma
     * w podsumowaniu „błąd", a udane nie ma podsumowania, i czy dialog wywołania pokazuje długość
     * wyniku oraz zapytanie i odpowiedź z wcięciami.
     *
     * Wyłapuje odmowę narzędzia pokazaną jak zwykły wynik — na pokazie nie byłoby widać, że model
     * dostał błąd — i odpowiedź w dialogu w jednej linii, nie do czytania.
     */
    test("marks tool errors and shows query and answer in the dialog", () => {
        const rows = runRows(sampleRun(), 2_000_000);
        const ok   = rows[2];

        expect(ok.summary).toBe("");
        expect(ok.detail?.meta).toContain(`${sampleToolCall().result.length} zn.`);
        expect(rows[3].summary).toBe("błąd");
        expect(ok.detail?.sections.map((section) => section.heading)).toEqual(["Zapytanie", "Odpowiedź"]);
        expect(ok.detail?.sections[1].body).toContain('\n  "tickets": [');
    });

    /**
     * Sprawdza, czy wiersz tury nie ma podsumowania, a dialog tury pokazuje tokeny w czterech
     * klasach i listę wywołań, o które poprosił model.
     *
     * Wyłapuje wiersz tury, który powtarza nazwy narzędzi stojących wiersz niżej, i dialog bez
     * wywołań: nie byłoby widać, ile tokenów poszło na zapis do cache ani co tura zleciła.
     */
    test("shows what a model turn asked for", () => {
        const turn = runRows(sampleRun(), 2_000_000)[1];

        expect(turn.summary).toBe("");
        expect(turn.detail?.sections[0].body).toContain("zapis do cache   3000");
        expect(turn.detail?.sections[1].body).toBe("find_tickets_vector, find_docs_vector");
    });

    /**
     * Sprawdza, czy dialog wiersza anonimizacji pokazuje pod wpisem logu tekst po anonimizacji
     * z długością, a dialog odpowiedzi — sam wpis logu.
     *
     * Wyłapuje dialog anonimizacji bez tekstu, który dostał model (nie dałoby się sprawdzić, co
     * zostało ze zgłoszenia po zamianie danych na znaczniki), i ten tekst doklejany do innych
     * kroków.
     */
    test("shows the anonymized text in the anonymize dialog only", () => {
        const rows = runRows(sampleRun(), 2_000_000);

        expect(rows[0].detail?.sections.map((section) => section.heading)).toEqual(["Wpis logu", "Tekst po anonimizacji"]);
        expect(rows[0].detail?.sections[1]).toMatchObject({ body: ANONYMIZED_TEXT, note: `to, co dostał model · ${ANONYMIZED_TEXT.length} zn.` });
        expect(rows[5].detail?.sections.map((section) => section.heading)).toEqual(["Wpis logu"]);
    });

    /**
     * Sprawdza, czy przebieg w toku kończy się wierszem tego, co trwa, z czasem od ostatniego
     * kroku w zegarze przeglądarki i bez dialogu.
     *
     * Wyłapuje brak wiersza w toku (konsola wyglądałaby na zatrzymaną w trakcie długiej tury
     * modelu) i czas liczony od początku przebiegu zamiast od ostatniego kroku.
     */
    test("ends a running run with a pending row", () => {
        const run  = sampleRun({ steps: sampleRun().steps.slice(0, 2), finishedAt: null, lastEventAt: 5_000 });
        const last = runRows(run, 7_500).at(-1);

        expect(last).toMatchObject({ kind: "pending", label: "↳ find_tickets_vector, find_docs_vector", duration: "2,5 s", detail: null });
    });
});

describe("pendingLabel", () => {
    /**
     * Sprawdza, co trwa po każdym rodzaju ostatniego kroku: bez kroków anonimizacja, po niej
     * pierwsza tura, po turze z narzędziami wiedzy — te narzędzia, po turze z samym narzędziem
     * odpowiedzi albo bez wywołań — odpowiedź, a po narzędziach i po odpowiedzi odesłanej do
     * poprawki — kolejna tura.
     *
     * Wyłapuje etykietę zgadywaną z wpisu logu albo pomyloną kolejność węzłów: konsola
     * pokazywałaby w toku narzędzia, gdy model już odpowiada, albo odwrotnie.
     */
    test.each([
        [[], "anonymize"],
        [[sampleStep("anonymize")], "agent · tura 1"],
        [[sampleStep("agent", { requested_tools: ["read_docs"] })], "↳ read_docs"],
        [[sampleStep("agent", { requested_tools: ["respond_search"] })], "respond"],
        [[sampleStep("agent")], "respond"],
        [[sampleStep("agent"), sampleStep("run_tools")], "agent · tura 2"],
        [[sampleStep("agent"), sampleStep("respond")], "agent · tura 2"],
    ])("after %j it is %s", (steps, label) => {
        expect(pendingLabel(steps)).toBe(label);
    });
});

describe("runSummary", () => {
    /**
     * Sprawdza, czy nagłówek przebiegu podaje tury, wywołania narzędzi, koszt i czas w polskiej
     * odmianie, a przy przebiegu w toku i zakończonym błędem dopisuje to na końcu.
     *
     * Wyłapuje sumy liczone z wyniku zamiast z kroków (przebieg z błędem pokazałby zero kosztu)
     * i złą odmianę liczebników.
     */
    test("counts turns, tools, cost and time and says how the run ended", () => {
        const finished = runSummary(sampleRun(), 2_000_000);
        const running  = runSummary(sampleRun({ finishedAt: null }), 1_005_000);
        const failed   = runSummary(sampleRun({ error: "503: anonimizator nie odpowiedział" }), 2_000_000);

        expect(finished).toBe("2 tury · 2 narzędzia · 0,069 USD · 27,4 s");
        expect(running).toBe("2 tury · 2 narzędzia · 0,069 USD · 5,0 s · w toku");
        expect(failed).toMatch(/· błąd$/);
        expect(runSummary(sampleRun({ steps: [sampleStep("agent", { usage: sampleUsage(0) })] }), 0)).toMatch(/^1 tura · 0 narzędzi/);
    });
});
