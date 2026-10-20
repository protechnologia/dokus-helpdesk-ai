/**
 * Description:
 * Rozbiór strumienia przebiegu (SSE) na zdarzenia. Trasy grafów `api` odpowiadają nim przy
 * nagłówku `Accept: text/event-stream`; `EventSource` przeglądarki nie umie wysłać żądania POST,
 * więc strumień czyta `fetch`, a zdarzenia wydziela ten plik.
 *
 * Przed — tekst, który przyszedł dwoma kawałkami, z urwanym drugim zdarzeniem:
 *
 *     "event: step\ndata: {\"node\": \"anonymize\"}\n\nevent: st"
 *
 * Po — `splitEvents()`:
 *
 *     { events: [{ event: "step", data: "{\"node\": \"anonymize\"}" }], rest: "event: st" }
 *
 * O czym pamiętać przy zmianach:
 *
 * - Zdarzenie kończy pusta linia; to, co stoi za ostatnią pustą linią, czeka na resztę
 *   w następnym kawałku (`rest`).
 * - `api` pisze każde zdarzenie w jednej linii danych, ale format SSE pozwala na kilka — wtedy
 *   łączy je znak nowej linii, jak w przeglądarce.
 * - Linie zaczynające się dwukropkiem to komentarze SSE i są pomijane.
 */

/** Jedno zdarzenie strumienia: nazwa i surowe dane (w `api` zawsze JSON). */
export interface SseEvent {
    event: string;  // np. "step", "result", "error"
    data:  string;  // np. '{"node": "anonymize", …}'
}

/**
 * Description:
 * Wydziela z tekstu strumienia pełne zdarzenia i oddaje resztę, która czeka na dalszy ciąg.
 * Końce linii `\r\n` traktuje jak `\n`. Zdarzenie bez nazwy dostaje nazwę `message`, jak w SSE.
 *
 * Example args:
 *     buffer="event: step\ndata: {}\n\nevent: res"
 *
 * Example result:
 *     { events: [{ event: "step", data: "{}" }], rest: "event: res" }
 */
export function splitEvents(
    buffer: string,  // np. "event: step\ndata: {}\n\nevent: res"
): { events: SseEvent[]; rest: string } {
    const normalized = buffer.replace(/\r\n/g, "\n");
    const blocks     = normalized.split("\n\n");
    const rest       = blocks.pop() ?? "";

    const events = blocks
        .map(parseBlock)
        .filter((event): event is SseEvent => event !== null);

    return { events, rest };
}

/**
 * Description:
 * Czyta strumień odpowiedzi i oddaje zdarzenia po kolei, w miarę jak przychodzą. Urwany koniec
 * strumienia bez pustej linii też jest zdarzeniem, o ile ma dane.
 *
 * Example args:
 *     body=response.body  // ReadableStream z fetch
 *
 * Example result:
 *     { event: "step", data: "…" }, { event: "step", data: "…" }, { event: "result", data: "…" }
 */
export async function* readEvents(
    body: ReadableStream<Uint8Array>,  // np. response.body
): AsyncGenerator<SseEvent> {
    const reader  = body.getReader();
    const decoder = new TextDecoder();
    let buffer    = "";

    while (true) {
        const { done, value } = await reader.read();

        // --- koniec strumienia: to, co zostało, jest ostatnim zdarzeniem albo niczym ---
        if (done) {
            const last = parseBlock(buffer + decoder.decode());

            if (last !== null) {
                yield last;
            }

            return;
        }

        const { events, rest } = splitEvents(buffer + decoder.decode(value, { stream: true }));

        buffer = rest;

        yield* events;
    }
}

/**
 * Description:
 * Zamienia jeden blok strumienia (linie do pustej linii) na zdarzenie albo `null`, gdy blok nie
 * niesie danych — sam komentarz albo pusty tekst.
 *
 * Example args:
 *     block="event: error\ndata: {\"detail\": \"…\"}"
 *
 * Example result:
 *     { event: "error", data: "{\"detail\": \"…\"}" }
 */
function parseBlock(
    block: string,  // np. "event: step\ndata: {}"
): SseEvent | null {
    let event      = "message";
    const data: string[] = [];

    for (const line of block.split("\n")) {
        // --- komentarz SSE albo pusta linia: nic nie niesie ---
        if (line === "" || line.startsWith(":")) {
            continue;
        }

        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        // Po dwukropku stoi zwykle jedna spacja, która nie należy do wartości (format SSE).
        const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");

        // --- nazwa zdarzenia ---
        if (field === "event") {
            event = value;
        }

        // --- linia danych; kilka linii łączy znak nowej linii ---
        if (field === "data") {
            data.push(value);
        }
    }

    // --- blok bez danych nie jest zdarzeniem ---
    if (data.length === 0) {
        return null;
    }

    return { event, data: data.join("\n") };
}
