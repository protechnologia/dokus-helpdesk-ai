/**
 * Description:
 * Propozycja odpowiedzi w wybranym wariancie i lista wariantów — przepisane z
 * `api/app/entry_routers/suggest/models.py`.
 *
 * | model              | trasa            |
 * |--------------------|------------------|
 * | `SuggestRequest`   | `POST /suggest`  |
 * | `SuggestResponse`  | `POST /suggest`  |
 * | `VariantsResponse` | `GET /variants`  |
 *
 * Kto czyta:
 * - `SuggestResponse` — `pages/App.tsx` wpisuje `text` do szkicu w zakładce „Dla klienta"
 *   (`pages/panels/ClientTab.tsx`), `pages/panels/NotesTab.tsx` pokazuje uwagi, a `pages/panels/AnswerPanel.tsx`
 *   źródła.
 * - `VariantsResponse` — `pages/panels/GraphButtons.tsx` rysuje z niego guziki wariantów.
 * - `SuggestRequest` — `pages/App.tsx` wysyła w nim zgłoszenie z lewego panelu i wybrany wariant.
 */

import type { LogItem, SourceItem, UsageItem } from "./common";
import type { TicketRequest } from "./ticket";

/** Zgłoszenie z wybranym wariantem odpowiedzi. */
export interface SuggestRequest extends TicketRequest {
    variant: string;  // np. "solution"
}

/** Propozycja odpowiedzi; `text` to `null`, gdy treści dla klienta nie ma. */
export interface SuggestResponse {
    variant:        string;         // np. "solution"
    text:           string | null;  // np. "Dzień dobry,\nprzesyłki…"
    internal_notes: string;         // np. "1: odcina zacięcie kolejki (zgł. 90001)"
    sources:        SourceItem[];
    usage:          UsageItem;
    log:            LogItem[];
}

/** Wariant odpowiedzi do narysowania jako guzik. */
export interface VariantInfo {
    name:          string;   // np. "questions"
    label:         string;   // np. "Jakie pytania zadać"
    requires_hits: boolean;  // np. false
}

/** Odpowiedź `GET /variants`. */
export interface VariantsResponse {
    variants: VariantInfo[];
}
