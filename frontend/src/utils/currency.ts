/**
 * Description:
 * Kwoty dla człowieka. Dziś jedna waluta, dolar, bo w nim liczą cenniki dostawców modeli.
 *
 * | funkcja       | przykład             |
 * |---------------|----------------------|
 * | `formatUsd()` | 0.0691 → "0,069 USD" |
 */

import { LOCALE } from "./locale";

/**
 * Description:
 * Koszt w dolarach z trzema miejscami po przecinku — sprawa kosztuje zwykle ułamek centa.
 *
 * Example args:
 *     usd=0.0691
 *
 * Example result:
 *     "0,069 USD"
 */
export function formatUsd(
    usd: number,  // np. 0.0691
): string {
    const amount = usd.toLocaleString(LOCALE, { minimumFractionDigits: 3, maximumFractionDigits: 3 });

    return `${amount} USD`;
}
