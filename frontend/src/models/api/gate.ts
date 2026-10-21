/**
 * Description:
 * Bramki jakości: werdykt w jednym kształcie dla bramki zamknięcia i bramki wysyłki oraz
 * żądanie bramki wysyłki — przepisane z `api/app/entry_routers/gate/models.py`.
 *
 * Kto czyta:
 * - `VerdictResponse` — `pages/panels/NotesTab.tsx` (zakładka „Dla wdrożeniowca"): werdykt, powody
 *   i wskazówka.
 * - `GateReplyRequest` — `pages/App.tsx` wysyła w nim treść z zakładki „Dla klienta" po kliknięciu
 *   „Sprawdź przed wysyłką".
 */

import type { LogItem, UsageItem } from "./common";

/** Wiadomość do klienta do sprawdzenia bramką wysyłki (`POST /gate/reply`). */
export interface GateReplyRequest {
    ticket_id: string;  // np. "90101"
    message:   string;  // np. "Dzień dobry, prosimy o…"
}

/** Werdykt bramki; zawsze z furtką dla człowieka (`overridable`). */
export interface VerdictResponse {
    verdict:       "pass" | "block";
    reasons:       string[];  // np. ["Nie widać, co zrobiono."]
    hint:          string;    // np. "Dopisz, co zmieniono."
    overridable:   boolean;   // zawsze true
    rules_version: number;    // np. 1
    usage:         UsageItem;
    log:           LogItem[];
}
