/**
 * Description:
 * Odpowiedź `POST /search` — rozpoznanie dla wdrożeniowca, przepisane z
 * `api/app/entry_routers/search/models.py`.
 *
 * Kto czyta: `pages/panels/NotesTab.tsx` (uwagi w zakładce „Dla wdrożeniowca") i
 * `pages/panels/AnswerPanel.tsx` (zakładka „Źródła"). Listy `queries` front nie pokazuje osobno:
 * wywołania narzędzi z argumentami i wynikami ma konsola przebiegu.
 */

import type { LogItem, SourceItem, UsageItem } from "./common";

/** Wywołanie narzędzia przez agenta w `/search`, bez wyniku. */
export interface AgentQuery {
    tool:                    string;                   // np. "find_tickets_vector"
    arguments:               Record<string, unknown>;  // np. {"problem": "Brak przesyłek"}
    dropped_below_threshold: number | null;            // np. 3; tylko wyszukiwanie po znaczeniu
}

/** Rozpoznanie: przeczytane źródła i uwagi dla wdrożeniowca w lekkim Markdownie. */
export interface SearchResponse {
    sources:        SourceItem[];
    internal_notes: string;  // np. "## Zgłoszenia historyczne\n- 90001: …"
    queries:        AgentQuery[];
    usage:          UsageItem;
    log:            LogItem[];
}
