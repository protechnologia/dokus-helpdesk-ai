/**
 * Description:
 * Co środkowy panel bierze z przebiegu: tekst dla klienta, tekst po anonimizacji i źródła. Panel
 * pokazuje jeden przebieg naraz — ostatni albo wczytany z konsoli — więc wszystko, co w nim
 * stoi, pochodzi z tego przebiegu, a nie z poprzednich.
 *
 * | funkcja             | skąd                                                    |
 * |---------------------|---------------------------------------------------------|
 * | `clientTextOf()`    | propozycja odpowiedzi, wynik „Popraw" albo szkic        |
 * |                     | sprawdzony bramką wysyłki; `null` przy innych grafach   |
 * | `anonymizedTextOf()`| krok `anonymize` strumienia: tekst, który dostał model  |
 * | `sourcesOf()`       | źródła rozpoznania i propozycji; inne grafy ich nie mają |
 *
 * Kto czyta: `pages/App.tsx` (szkic dla klienta po zmianie pokazanego przebiegu)
 * i `pages/panels/AnswerPanel.tsx` (zakładki, tekst po anonimizacji przy przebiegu w toku
 * i po błędzie).
 *
 * O czym pamiętać przy zmianach:
 *
 * - Przebieg bez tekstu dla klienta (rozpoznanie, karta, bramka zamknięcia, wariant bez treści)
 *   daje `null`, a strona czyści wtedy szkic: stary tekst z innego przebiegu udawałby wynik
 *   tego.
 * - Bramka wysyłki nie zmienia tekstu, tylko go ocenia, więc jej tekstem jest szkic, który
 *   sprawdziła (`draftInput`).
 */

import type { SourceItem } from "../models/api/common";
import type { Run } from "../models/runs/run";

/**
 * Description:
 * Tekst dla klienta, który niesie przebieg: propozycja odpowiedzi z treścią, wynik „Popraw" albo
 * szkic sprawdzony bramką wysyłki; `null`, gdy przebieg tekstu dla klienta nie daje albo jeszcze
 * nie skończył.
 *
 * Example args:
 *     run=Run(kind="polish", outcome={ kind: "polish", result: { text: "Dzień dobry, …" } })
 *
 * Example result:
 *     "Dzień dobry, …"
 */
export function clientTextOf(
    run: Run,  // np. przebieg pokazany w środkowym panelu
): string | null {
    const outcome = run.outcome;

    // --- propozycja odpowiedzi: wariant bez treści dla klienta nie ma tekstu ---
    if (outcome?.kind === "suggest") {
        return outcome.result.text;
    }

    // --- „Popraw": ten sam sens w poprawnej formie ---
    if (outcome?.kind === "polish") {
        return outcome.result.text;
    }

    // --- bramka wysyłki: tekst, który oceniła ---
    if (outcome?.kind === "gate_reply") {
        return run.draftInput;
    }

    return null;
}

/**
 * Description:
 * Tekst zgłoszenia po anonimizacji z kroku `anonymize` — ten, który dostał model; `null`, dopóki
 * krok nie przyszedł albo gdy przebieg padł przed nim.
 *
 * Example args:
 *     run=Run(steps=[StepItem(node="anonymize", anonymized_text="{IMIĘ} zgłasza…"), …])
 *
 * Example result:
 *     "{IMIĘ} zgłasza…"
 */
export function anonymizedTextOf(
    run: Run,  // np. przebieg pokazany w środkowym panelu
): string | null {
    const step = run.steps.find((one) => one.node === "anonymize");

    return step?.anonymized_text ?? null;
}

/**
 * Description:
 * Źródła przebiegu: tylko rozpoznanie i propozycja odpowiedzi czytają materiał, reszta grafów
 * źródeł nie ma.
 *
 * Example args:
 *     run=Run(outcome={ kind: "search", result: { sources: [ … ], … } })
 *
 * Example result:
 *     [{ source: "tickets", item_id: "90001", title: "…", date: "2026-03-14" }, …]
 */
export function sourcesOf(
    run: Run,  // np. przebieg pokazany w środkowym panelu
): SourceItem[] {
    const outcome = run.outcome;

    // --- grafy, które czytają materiał ---
    if (outcome?.kind === "search" || outcome?.kind === "suggest") {
        return outcome.result.sources;
    }

    return [];
}
