/**
 * Description:
 * Testy rozbioru strumienia przebiegu (`frontend/src/api/sse.ts`): czy z tekstu SSE wychodzą te
 * same zdarzenia, które wysłała trasa `api`, także gdy tekst przychodzi w kawałkach.
 */

import { describe, expect, test } from "vitest";

import { readEvents, splitEvents } from "../../../frontend/src/api/sse";

/**
 * Description:
 * Strumień, który oddaje podane kawałki tekstu po kolei, jak `response.body` z `fetch`.
 *
 * Example args:
 *     chunks=["event: st", "ep\ndata: {}\n\n"]
 *
 * Example result:
 *     ReadableStream<Uint8Array> z dwoma kawałkami
 */
function streamOf(
    chunks: string[],  // np. ["event: st", "ep\ndata: {}\n\n"]
): ReadableStream<Uint8Array> {
    const encoder = new TextEncoder();

    return new ReadableStream({
        start(controller) {
            chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
            controller.close();
        },
    });
}

describe("splitEvents", () => {
    /**
     * Sprawdza, czy z tekstu z dwoma pełnymi zdarzeniami i początkiem trzeciego wychodzą dwa
     * zdarzenia z nazwą i danymi, a początek trzeciego zostaje jako reszta.
     *
     * Wyłapuje rozbiór, który gubi urwany koniec albo oddaje go jako zdarzenie: krok, który
     * przyszedł w dwóch kawałkach, zniknąłby z konsoli albo trafiłby do niej dwa razy.
     */
    test("splits whole events and keeps the unfinished rest", () => {
        const { events, rest } = splitEvents('event: step\ndata: {"a":1}\n\nevent: result\ndata: {"b":2}\n\nevent: st');

        expect(events).toEqual([
            { event: "step", data: '{"a":1}' },
            { event: "result", data: '{"b":2}' },
        ]);
        expect(rest).toBe("event: st");
    });

    /**
     * Sprawdza, czy końce linii `\r\n` dzielą zdarzenia tak samo jak `\n`.
     *
     * Wyłapuje rozbiór, który przy końcach linii z Windows (proxy, inny serwer) nie znajduje
     * pustej linii i nie oddaje żadnego zdarzenia aż do końca przebiegu.
     */
    test("treats CRLF line endings like LF", () => {
        const { events } = splitEvents("event: step\r\ndata: {}\r\n\r\n");

        expect(events).toEqual([{ event: "step", data: "{}" }]);
    });

    /**
     * Sprawdza, czy kilka linii danych łączy znak nowej linii, komentarz SSE jest pomijany,
     * a zdarzenie bez nazwy dostaje nazwę `message`.
     *
     * Wyłapuje rozbiór, który bierze tylko ostatnią linię danych albo komentarz jako dane:
     * zdarzenie z wieloliniowymi danymi przyszłoby urwane i JSON by się nie rozebrał.
     */
    test("joins data lines, skips comments and names events without a name", () => {
        const { events } = splitEvents(": ping\ndata: pierwsza\ndata: druga\n\n");

        expect(events).toEqual([{ event: "message", data: "pierwsza\ndruga" }]);
    });

    /**
     * Sprawdza, czy blok bez danych (sam komentarz albo sama nazwa) nie jest zdarzeniem.
     *
     * Wyłapuje zdarzenia z pustymi danymi, na których `JSON.parse` w kliencie skończyłby
     * przebieg błędem.
     */
    test("ignores blocks without data", () => {
        const { events } = splitEvents(": ping\n\nevent: step\n\n");

        expect(events).toEqual([]);
    });
});

describe("readEvents", () => {
    /**
     * Sprawdza, czy zdarzenia przychodzące w kawałkach pociętych w środku nazwy i w środku
     * danych wychodzą w całości i po kolei, a ostatnie bez pustej linii na końcu też wychodzi.
     *
     * Wyłapuje czytanie, które rozbiera każdy kawałek osobno: kroki pocięte przez sieć ginęłyby,
     * a wynik na samym końcu strumienia nie dotarłby do strony.
     */
    test("reassembles events split across chunks", async () => {
        const stream = streamOf(["event: st", 'ep\ndata: {"n":', '1}\n\nevent: result\ndata: {}']);
        const events = [];

        for await (const event of readEvents(stream)) {
            events.push(event);
        }

        expect(events).toEqual([
            { event: "step", data: '{"n":1}' },
            { event: "result", data: "{}" },
        ]);
    });
});
