/**
 * Description:
 * Przebieg grafu w sesji strony — model frontu, nie `api`. Tworzy go i uzupełnia `useRuns()`,
 * a czytają konsola, środkowy panel i belka liczników.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Czasy `startedAt`, `lastEventAt` i `finishedAt` są w zegarze przeglądarki i mierzą czekanie
 *   człowieka; czasy kroków (`steps`) pochodzą z zegara `api`.
 * - Przebieg w toku ma `finishedAt` równe `null`; po końcu ma `outcome` albo `error`, nigdy oba.
 */

import type { GraphKind, GraphOutcome } from "./graph";
import type { StepItem } from "../api/step";

/** Jeden przebieg grafu w sesji strony. */
export interface Run {
    id:          number;               // np. 3
    kind:        GraphKind;            // np. "suggest"
    title:       string;               // np. "Rozwiązanie"
    ticketId:    string;               // np. "90101"
    draftInput:  string | null;        // szkic, na którym pracowała bramka wysyłki albo „Popraw"
    startedAt:   number;               // ms od epoki: wysłanie żądania
    lastEventAt: number;               // ms od epoki: start albo ostatni krok
    finishedAt:  number | null;        // null, dopóki przebieg trwa
    steps:       StepItem[];
    outcome:     GraphOutcome | null;  // null w toku i po błędzie
    error:       string | null;        // np. "503: anonimizator nie odpowiedział"
}
