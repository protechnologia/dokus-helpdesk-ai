/**
 * Description:
 * Czas dla człowieka: ile coś trwało i w której chwili przebiegu się zaczęło.
 *
 * | funkcja             | przykład                                  |
 * |---------------------|-------------------------------------------|
 * | `formatDuration()`  | 84.2 → "84 ms", 27400 → "27,4 s"          |
 * | `formatClock()`     | 3040 → "00:03.0"                          |
 * | `formatTimestamp()` | 2026-10-19 09:12 czasu lokalnego → "2026-10-19 09:12" |
 */

import { LOCALE } from "./locale";

/**
 * Description:
 * Czas trwania: poniżej sekundy w milisekundach, dłuższy w sekundach z jednym miejscem po
 * przecinku.
 *
 * Example args:
 *     ms=27400
 *
 * Example result:
 *     "27,4 s"
 */
export function formatDuration(
    ms: number,  // np. 27400
): string {
    // --- krótkie wywołania narzędzi: sekundy z przecinkiem pokazałyby same zera ---
    if (ms < 1000) {
        return `${Math.round(ms)} ms`;
    }

    const seconds = (ms / 1000).toLocaleString(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

    return `${seconds} s`;
}

/**
 * Description:
 * Chwila od początku przebiegu jako zegar minuty:sekundy.dziesiąte; chwila przed początkiem
 * (rozjazd zegarów) to zero.
 *
 * Example args:
 *     ms=3040
 *
 * Example result:
 *     "00:03.0"
 */
export function formatClock(
    ms: number,  // np. 3040
): string {
    const tenths  = Math.max(0, Math.floor(ms / 100));
    const minutes = Math.floor(tenths / 600);
    const seconds = Math.floor((tenths % 600) / 10);

    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths % 10}`;
}

/**
 * Description:
 * Chwila w czasie lokalnym w kształcie dat komentarzy wątku: rok-miesiąc-dzień i godzina
 * z minutami.
 *
 * Example args:
 *     date=new Date(2026, 9, 19, 9, 12)
 *
 * Example result:
 *     "2026-10-19 09:12"
 */
export function formatTimestamp(
    date: Date,  // np. new Date()
): string {
    const pad = (value: number) => String(value).padStart(2, "0");

    const day  = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;

    return `${day} ${time}`;
}
