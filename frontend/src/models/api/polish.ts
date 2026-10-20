/**
 * Description:
 * „Popraw": notatki wdrożeniowca na wejściu i ten sam sens w poprawnej formie na wyjściu —
 * przepisane z `api/app/entry_routers/polish/models.py`.
 *
 * Kto czyta: `pages/App.tsx` — wysyła treść z zakładki „Dla klienta" po kliknięciu „Popraw"
 * i wpisuje poprawiony tekst z powrotem do tej zakładki (`pages/panels/ClientTab.tsx`).
 */

import type { LogItem, UsageItem } from "./common";

/** Notatki do przepisania (`POST /polish`). */
export interface PolishRequest {
    ticket_id: string;  // np. "90101"
    text:      string;  // np. "kolejka stala, juz dziala"
}

/** Wynik „Popraw". */
export interface PolishResponse {
    text:  string;  // np. "Dzień dobry, przesyłki z e-Doręczeń już docierają…"
    usage: UsageItem;
    log:   LogItem[];
}
