/**
 * Description:
 * Testy funkcji bez wiedzy o dziedzinie (`frontend/src/utils/`): odmiana przy liczbie, zegar
 * przebiegu, czas trwania i koszt — to, co czyta się na belce i w konsoli — oraz przygotowanie
 * JSON-a i Markdownu do czytania.
 */

import { describe, expect, test } from "vitest";

import { formatTokens, plural } from "../../../frontend/src/utils/count";
import { formatUsd } from "../../../frontend/src/utils/currency";
import { parseJsonObject } from "../../../frontend/src/utils/json";
import { linesAsParagraphs } from "../../../frontend/src/utils/markdown";
import { formatClock, formatDuration, formatTimestamp } from "../../../frontend/src/utils/time";

// Odmiana rzeczownika „tura" w testach liczebników.
const TURA: [string, string, string] = ["tura", "tury", "tur"];

describe("plural", () => {
    /**
     * Sprawdza polską odmianę przy liczbie: 1 tura, 2–4 tury (także 22), 5 i więcej tur, a także
     * 0 i 12–14 tur.
     *
     * Wyłapuje odmianę po samej ostatniej cyfrze, która dałaby „12 tury", i liczbę pojedynczą
     * przy zerze.
     */
    test.each([
        [1, "1 tura"],
        [2, "2 tury"],
        [4, "4 tury"],
        [5, "5 tur"],
        [12, "12 tur"],
        [14, "14 tur"],
        [22, "22 tury"],
        [0, "0 tur"],
    ])("%i → %s", (count, expected) => {
        expect(plural(count, TURA)).toBe(expected);
    });
});

describe("time", () => {
    /**
     * Sprawdza zegar przebiegu (minuty, sekundy, dziesiąte; chwila przed początkiem to zero) i czas
     * trwania (poniżej sekundy w milisekundach, dłużej w sekundach z przecinkiem).
     *
     * Wyłapuje zegar, który przy rozjeździe zegarów pokazuje liczby ujemne, i czas wywołania
     * narzędzia pokazany jako „0,1 s" zamiast w milisekundach.
     */
    test("formats clocks and durations", () => {
        expect(formatClock(3_040)).toBe("00:03.0");
        expect(formatClock(61_500)).toBe("01:01.5");
        expect(formatClock(-200)).toBe("00:00.0");
        expect(formatDuration(84.2)).toBe("84 ms");
        expect(formatDuration(27_400)).toBe("27,4 s");
        expect(formatTimestamp(new Date(2026, 9, 9, 7, 5))).toBe("2026-10-09 07:05");
    });
});

describe("count and currency", () => {
    /**
     * Sprawdza koszt z trzema miejscami po przecinku i tokeny w tysiącach od tysiąca.
     *
     * Wyłapuje koszt zaokrąglony do centów (sprawa za 0,004 USD wyglądałaby na darmową) i tokeny
     * z kropką dziesiętną zamiast polskiego zapisu.
     */
    test("formats cost and tokens", () => {
        expect(formatUsd(0.0041)).toBe("0,004 USD");
        expect(formatTokens(999)).toBe("999");
        expect(formatTokens(144_310)).toBe("144 tys.");
    });
});

describe("json", () => {
    /**
     * Sprawdza, czy obiekt i tablica JSON wracają rozebrane, a tekst, który nie jest JSON-em,
     * i pojedyncza wartość JSON (napis, liczba, `null`) dają `null`.
     *
     * Wyłapuje przeglądarkę JSON-a uruchamianą na wpisie logu albo na samym napisie: dialog
     * pokazałby wtedy pusty albo jednopoziomowy widok zamiast tekstu.
     */
    test("parses objects and arrays only", () => {
        expect(parseJsonObject('{"cards":[{"ticket_id":"90001"}]}')).toEqual({ cards: [{ ticket_id: "90001" }] });
        expect(parseJsonObject("[1, 2]")).toEqual([1, 2]);
        expect(parseJsonObject("zanonimizowano 412 zn.")).toBeNull();
        expect(parseJsonObject('"napis"')).toBeNull();
        expect(parseJsonObject("42")).toBeNull();
        expect(parseJsonObject("null")).toBeNull();
    });
});

describe("markdown", () => {
    /**
     * Sprawdza, czy kolejne zwykłe linie (notatki „Ad. 1.", „Ad. 2.") dostają pustą linię między
     * sobą, a nagłówek, punkty listy i linie bloku kodu zostają bez zmian.
     *
     * Wyłapuje notatki sklejone przez Markdown w jeden blok tekstu i pustą linię wstawioną w listę
     * albo w blok kodu, która rozbiłaby listę na osobne listy albo zmieniła kod.
     */
    test("turns plain lines into paragraphs and keeps structure", () => {
        const notes = "Ad. 1. odcina kolejkę\nAd. 2. odcina załącznik\n## Kod\n- linia 12\n- linia 14\n```\na\nb\n```";

        expect(linesAsParagraphs(notes)).toBe(
            "Ad. 1. odcina kolejkę\n\nAd. 2. odcina załącznik\n## Kod\n- linia 12\n- linia 14\n```\na\nb\n```",
        );
    });
});
