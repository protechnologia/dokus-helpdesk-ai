/**
 * Description:
 * Tekst JSON do czytania przez człowieka.
 *
 * | funkcja             | przykład                                       |
 * |---------------------|------------------------------------------------|
 * | `prettyJson()`      | '{"a":1}' → '{\n  "a": 1\n}'; "abc" → "abc"     |
 * | `parseJsonObject()` | '{"a":1}' → { a: 1 }; '"abc"' i "abc" → null    |
 */

/**
 * Description:
 * Tekst JSON z wcięciami; tekst, który nie jest JSON-em, zostaje znak w znak.
 *
 * Example args:
 *     text='{"tickets":[{"ticket_id":"90001"}]}'
 *
 * Example result:
 *     '{\n  "tickets": [\n    {\n      "ticket_id": "90001"\n    }\n  ]\n}'
 */
export function prettyJson(
    text: string,  // np. wynik narzędzia
): string {
    try {
        return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
        return text;
    }
}

/**
 * Description:
 * Obiekt albo tablica z tekstu JSON; `null`, gdy tekst nie jest JSON-em albo jest nim tylko
 * pojedyncza wartość (napis, liczba) — takiej nie ma czego zwijać.
 *
 * Example args:
 *     text='{"tickets":[{"ticket_id":"90001"}]}'
 *
 * Example result:
 *     { tickets: [{ ticket_id: "90001" }] }
 */
export function parseJsonObject(
    text: string,  // np. wynik narzędzia
): object | null {
    try {
        const parsed: unknown = JSON.parse(text);

        return typeof parsed === "object" && parsed !== null ? parsed : null;
    } catch {
        return null;
    }
}
