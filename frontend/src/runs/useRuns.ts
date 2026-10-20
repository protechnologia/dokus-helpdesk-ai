/**
 * Description:
 * Przebiegi grafów od otwarcia strony: uruchomienie, kroki dopisywane w miarę jak przychodzą,
 * wynik albo błąd na końcu. Z tej listy czytają konsola, środkowy panel i belka liczników.
 *
 * Flow:
 *     1. `start()` dopisuje przebieg w toku i woła `runGraph()` z `api/client.ts`.
 *     2. Każdy krok strumienia trafia do `steps` przebiegu, razem z chwilą, w której przyszedł.
 *     3. Na końcu przebieg dostaje `outcome` albo `error` i `finishedAt`; `start()` oddaje go
 *        wołającemu, żeby ten mógł np. wpisać propozycję do szkicu dla klienta.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Przebiegi żyją w pamięci strony: odświeżenie strony je czyści, i tak ma być — liczniki belki
 *   liczą się „od otwarcia strony".
 * - Czasy po stronie przeglądarki (`startedAt`, `lastEventAt`, `finishedAt`) mierzą czekanie
 *   człowieka; czasy kroków pochodzą z zegara `api` i służą tylko do odstępów między krokami.
 */

import { useCallback, useRef, useState } from "react";

import { runGraph } from "../api/client";
import { ApiError } from "../errors/ApiError";
import type { GraphKind, GraphOutcome } from "../models/runs/graph";
import type { Run } from "../models/runs/run";

/** To, co oddaje `useRuns()`. */
export interface RunsApi {
    runs:    Run[];
    running: boolean;
    start:   (
        kind:       GraphKind,
        title:      string,
        ticketId:   string,
        body:       object,
        draftInput: string | null,
    ) => Promise<Run>;
}

/**
 * Description:
 * Hook z listą przebiegów i funkcją, która uruchamia nowy. Naraz trwa najwyżej jeden przebieg —
 * guziki są wtedy wyłączone, więc lista nie musi rozstrzygać kolejności.
 *
 * Example args:
 *     (brak)
 *
 * Example result:
 *     { runs: [Run(…)], running: false,
 *       start: (kind, title, ticketId, body, draftInput) => Promise<Run> }
 */
export function useRuns(): RunsApi {
    // Przebiegi od otwarcia strony, w kolejności uruchomienia.
    const [runs, setRuns] = useState<Run[]>([]);
    // Numer następnego przebiegu; ref, bo jego zmiana nie ma przerysowywać strony.
    const nextId          = useRef(1);

    const start = useCallback(async (
        kind:       GraphKind,      // np. "suggest"
        title:      string,         // np. "Rozwiązanie"
        ticketId:   string,         // np. "90101"
        body:       object,         // np. { ticket_id: "90101", body: "…", variant: "solution" }
        draftInput: string | null,  // np. szkic sprawdzany bramką wysyłki; null przy grafach na zgłoszeniu
    ): Promise<Run> => {
        const now = Date.now();
        let run: Run = {
            id:          nextId.current++,
            kind,
            title,
            ticketId,
            draftInput,
            startedAt:   now,
            lastEventAt: now,
            finishedAt:  null,
            steps:       [],
            outcome:     null,
            error:       null,
        };

        // Lokalna kopia przebiegu i lista w stanie zmieniają się razem: kopię oddaje się
        // wołającemu, bo stan Reacta odświeży się dopiero po zakończeniu tej funkcji.
        const update = (changes: Partial<Run>) => {
            run = { ...run, ...changes };

            const changed = run;

            setRuns((all) => all.map((other) => (other.id === changed.id ? changed : other)));
        };

        setRuns((all) => [...all, run]);

        try {
            const outcome: GraphOutcome = await runGraph(kind, body, (step) => {
                update({ steps: [...run.steps, step], lastEventAt: Date.now() });
            });

            update({ outcome, finishedAt: Date.now() });
        } catch (error) {
            // --- błąd `api` ma opis dla człowieka; inny wyjątek to usterka frontu ---
            const message = error instanceof ApiError ? error.message : `błąd frontu: ${String(error)}`;

            update({ error: message, finishedAt: Date.now() });
        }

        return run;
    }, []);

    const running = runs.some((run) => run.finishedAt === null);

    return { runs, running, start };
}
