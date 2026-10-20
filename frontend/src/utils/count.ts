/**
 * Description:
 * Liczności dla człowieka: duże liczby w skrócie i liczba z rzeczownikiem w polskiej odmianie.
 *
 * | funkcja          | przykład                               |
 * |------------------|----------------------------------------|
 * | `formatTokens()` | 144310 → "144 tys."                    |
 * | `plural()`       | (6, ["tura", "tury", "tur"]) → "6 tur" |
 */

import { LOCALE } from "./locale";

/**
 * Description:
 * Liczba tokenów: od tysiąca w tysiącach, zaokrąglona, bo na belce liczy się rząd wielkości.
 *
 * Example args:
 *     tokens=144310
 *
 * Example result:
 *     "144 tys."
 */
export function formatTokens(
    tokens: number,  // np. 144310
): string {
    if (tokens < 1000) {
        return String(tokens);
    }

    return `${Math.round(tokens / 1000).toLocaleString(LOCALE)} tys.`;
}

/**
 * Description:
 * Liczba z rzeczownikiem w polskiej odmianie: jeden, dwa–cztery (bez 12–14) i pozostałe.
 *
 * Example args:
 *     count=6
 *     forms=["tura", "tury", "tur"]
 *
 * Example result:
 *     "6 tur"
 */
export function plural(
    count: number,                    // np. 6
    forms: [string, string, string],  // np. ["tura", "tury", "tur"]
): string {
    const lastDigit = count % 10;
    const lastTwo   = count % 100;

    // --- jeden: „1 tura" ---
    if (count === 1) {
        return `${count} ${forms[0]}`;
    }

    // --- 2–4, ale nie 12–14: „3 tury", „22 tury" ---
    if (lastDigit >= 2 && lastDigit <= 4 && (lastTwo < 12 || lastTwo > 14)) {
        return `${count} ${forms[1]}`;
    }

    // --- reszta, także zero: „0 tur", „12 tur" ---
    return `${count} ${forms[2]}`;
}
