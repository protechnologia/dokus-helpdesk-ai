/**
 * Description:
 * Który graf uruchomił guzik i jaki wynik z niego przyszedł. Każdy z sześciu grafów oddaje wynik
 * innego kształtu, a środkowy panel musi wiedzieć, co dostał, żeby narysować uwagi, werdykt
 * albo kartę zgłoszenia. Wynik nosi więc ze sobą nazwę grafu (`kind`), a TypeScript po tej
 * nazwie sam wie, jakie pola ma `result` — bez rzutowania w każdym panelu.
 *
 * Do czego:
 * - `GraphKind` — guziki (`pages/panels/GraphButtons.tsx`, guziki pod treścią dla klienta)
 *   mówią nim, który graf uruchomić; `api/client.ts` wybiera po nim trasę, a przebieg
 *   (`Run.kind`) pamięta go, zanim przyjdzie wynik.
 * - `GraphOutcome` — wynik przebiegu (`Run.outcome`). Czytają go
 *   `pages/panels/AnswerPanel.tsx` (tytuł i zakładka na start), `pages/panels/NotesTab.tsx`
 *   (uwagi, werdykt albo karta), `pages/panels/ClientTab.tsx` (czy wariant dał treść dla
 *   klienta) i `pages/App.tsx` (propozycję albo wynik „Popraw" wpisuje do szkicu dla klienta).
 *
 * | graf           | guzik                                   | wynik             |
 * |----------------|-----------------------------------------|-------------------|
 * | `search`       | Rozpoznanie                             | `SearchResponse`  |
 * | `suggest`      | warianty z `GET /variants`              | `SuggestResponse` |
 * | `parse_ticket` | Karta zgłoszenia                        | `TicketCard`      |
 * | `gate_close`   | Bramka zamknięcia                       | `VerdictResponse` |
 * | `gate_reply`   | Sprawdź przed wysyłką (pod treścią)     | `VerdictResponse` |
 * | `polish`       | Popraw (pod treścią)                    | `PolishResponse`  |
 *
 * Przykład — środkowy panel rozpoznaje wynik po nazwie grafu:
 *
 *     switch (outcome.kind) {
 *         case "gate_close": return <Verdict verdict={outcome.result} />;  // result: VerdictResponse
 *         case "parse_ticket": return <Card card={outcome.result} />;      // result: TicketCard
 *     }
 *
 * O czym pamiętać przy zmianach:
 *
 * - Nazwy grafów są takie jak pakiety w `api/app/agent_graphs/`; nowy graf z guzikiem to nowa
 *   nazwa tutaj, trasa w `api/client.ts` i przypadek w środkowym panelu — kompilator wskaże
 *   miejsca, które go nie obsługują.
 */

import type { VerdictResponse } from "../api/gate";
import type { TicketCard } from "../api/parseTicket";
import type { PolishResponse } from "../api/polish";
import type { SearchResponse } from "../api/search";
import type { SuggestResponse } from "../api/suggest";

/** Graf, który front uruchamia. */
export type GraphKind = "search" | "suggest" | "parse_ticket" | "gate_close" | "gate_reply" | "polish";

/**
 * Guzik grafu w pasie nad kolumnami: który graf uruchomić na zgłoszeniu, jak przebieg nazwać
 * w konsoli i — przy propozycji odpowiedzi — który wariant. Listę rysuje
 * `pages/panels/GraphButtons.tsx`, a kliknięcie obsługuje `pages/App.tsx`.
 */
export interface GraphAction {
    kind:     "search" | "suggest" | "parse_ticket" | "gate_close";
    title:    string;  // np. "Rozwiązanie"
    variant?: string;  // np. "solution"; tylko przy `suggest`
}

/** Wynik przebiegu razem z grafem, który go dał — po `kind` widać kształt `result`. */
export type GraphOutcome =
    | { kind: "search";       result: SearchResponse }
    | { kind: "suggest";      result: SuggestResponse }
    | { kind: "parse_ticket"; result: TicketCard }
    | { kind: "gate_close";   result: VerdictResponse }
    | { kind: "gate_reply";   result: VerdictResponse }
    | { kind: "polish";       result: PolishResponse };
