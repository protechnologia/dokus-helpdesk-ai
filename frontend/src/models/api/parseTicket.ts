/**
 * Description:
 * Karta zgłoszenia z `POST /parse-ticket` — tak zgłoszenie wyglądałoby w bazie wiedzy;
 * przepisana z `api/app/entry_routers/parse_ticket/models.py`.
 *
 * Kto czyta: `pages/panels/NotesTab.tsx` — zakładka „Dla wdrożeniowca" pokazuje kartę pole po polu
 * po kliknięciu „Karta zgłoszenia".
 */

import type { LogItem, UsageItem } from "./common";

/** Karta zgłoszenia: pola kontraktu sparsowanego zgłoszenia, bez wersji słownika. */
export interface TicketCard {
    ticket_id:         string;    // np. "90101"
    date:              string;    // np. "2026-10-19"
    component:         string;    // np. "e-Doręczenia"
    problem:           string;
    symptoms:          string;
    error_codes:       string[];  // np. ["Nie udało się pobrać listy przesyłek"]
    cause:             string;
    excluded_causes:   string[];  // np. ["Brak miejsca na dysku"]
    solution:          string;
    resolution:        string;    // np. "bez_zmian_w_systemie"
    questions_summary: string;
    useful:            boolean;   // np. true — czy karta przyda się przy innej sprawie
    useful_reason:     string;
    usage:             UsageItem;
    log:               LogItem[];
}
