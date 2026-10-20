/**
 * Description:
 * Strona frontu pokazowego: belka z modelem i licznikami, pas guzików grafów, a pod nimi
 * zgłoszenie, odpowiedź i konsola przebiegu. Trzyma stan, który dzielą panele — zgłoszenie,
 * szkic dla klienta, przebiegi i to, który z nich pokazuje środkowy panel — i jako jedyna
 * uruchamia grafy; panele tylko go pokazują i zgłaszają, co kliknięto.
 *
 * | stan       | kto zmienia                                  | kto czyta                          |
 * |------------|----------------------------------------------|------------------------------------|
 * | zgłoszenie | `TicketPanel` (pola, wątek, przykłady)       | guziki grafów                      |
 * | szkic      | `ClientTab` (edycja), pokazany przebieg      | „Sprawdź przed wysyłką", „Popraw"  |
 * | przebiegi  | `useRuns()` po kliknięciu guzika             | `TopBar`, `AnswerPanel`, konsola   |
 * | pokazany   | nowy przebieg, guzik „pokaż" w konsoli       | `AnswerPanel`, konsola             |
 * | instancja  | `GET /instance`, `/variants` na starcie      | `TopBar`, `GraphButtons`           |
 *
 * Flow:
 *     1. Przy starcie strona czyta stan instancji i warianty odpowiedzi.
 *     2. Guzik nad kolumnami uruchamia graf na zgłoszeniu (`runOnTicket()`), a guzik pod
 *        szkicem — bramkę wysyłki albo „Popraw" na szkicu (`runOnDraft()`). Nowy przebieg
 *        staje się pokazanym.
 *     3. Gdy pokazany przebieg się skończy albo człowiek wczyta inny z konsoli, szkic dla klienta
 *        bierze tekst tego przebiegu (`clientTextOf()`), a bez tekstu jest pusty.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Naraz trwa najwyżej jeden przebieg: guziki są wtedy wyłączone.
 * - Szkic należy do pokazanego przebiegu: nowy przebieg albo wczytanie innego z konsoli
 *   zastępuje go, także poprawiony ręcznie. Stary tekst przy przebiegu, który tekstu nie dał
 *   (rozpoznanie, karta), udawałby jego wynik.
 */

import { App as AntApp } from "antd";
import { useEffect, useState } from "react";

import { getInstance, getVariants } from "../api/client";
import { EXAMPLES } from "../data/examples";
import type { InstanceResponse } from "../models/api/instance";
import type { VariantInfo } from "../models/api/suggest";
import type { TicketRequest } from "../models/api/ticket";
import type { GraphAction } from "../models/runs/graph";
import { Columns } from "./Columns";
import { AnswerPanel } from "./panels/AnswerPanel";
import { ConsolePanel } from "./panels/ConsolePanel";
import { GraphButtons } from "./panels/GraphButtons";
import { TicketPanel } from "./panels/TicketPanel";
import { TopBar } from "./panels/TopBar";
import { clientTextOf } from "../runs/answer";
import { sessionTotals } from "../runs/totals";
import { useRuns } from "../runs/useRuns";

// Co ile odświeża się czas przebiegu w toku (belka, konsola); 200 ms to dziesiąte części sekundy
// bez migania.
const TICK_MS = 200;

/**
 * Description:
 * Cała strona: stan dzielony przez panele i uruchamianie grafów.
 *
 * Example args:
 *     (brak)
 *
 * Example result:
 *     <div className="page"> z belką, guzikami i trzema kolumnami
 */
export function App() {
    // Komunikaty w rogu strony (błąd odczytu instancji albo wariantów).
    const { message }              = AntApp.useApp();
    // Zgłoszenie z lewego panelu, na którym działają guziki grafów; na start pierwszy przykład.
    const [ticket, setTicket]      = useState<TicketRequest>(EXAMPLES[0].ticket);
    // Szkic wiadomości do klienta z zakładki „Dla klienta"; wypełnia go pokazany przebieg.
    const [draft, setDraft]        = useState("");
    // Model i stan materiałów z `GET /instance` do belki; null, dopóki odpowiedź nie przyjdzie.
    const [instance, setInstance]  = useState<InstanceResponse | null>(null);
    // Warianty odpowiedzi z `GET /variants`, z których pas rysuje guziki.
    const [variants, setVariants]  = useState<VariantInfo[]>([]);
    // Przebiegi od otwarcia strony, czy któryś trwa, i funkcja, która uruchamia nowy.
    const { runs, running, start } = useRuns();
    // Numer przebiegu wczytanego z konsoli do środkowego panelu; null — panel pokazuje ostatni.
    const [shownId, setShownId]    = useState<number | null>(null);
    // Bieżąca chwila, tykająca w trakcie przebiegu, żeby czasy w belce i konsoli rosły na żywo.
    const now                      = useNow(running);

    // --- przy starcie: stan instancji do belki i warianty do guzików ---
    useEffect(() => {
        getInstance()
            .then(setInstance)
            .catch((error: Error) => message.error(`Stan instancji: ${error.message}`));
        getVariants()
            .then((response) => setVariants(response.variants))
            .catch((error: Error) => message.error(`Warianty odpowiedzi: ${error.message}`));
    }, [message]);

    // Przebieg w środkowym panelu: wczytany z konsoli albo ostatni.
    const shown = runs.find((run) => run.id === shownId) ?? runs.at(-1) ?? null;

    // --- pokazany przebieg skończył się albo człowiek wczytał inny: szkic to jego tekst ---
    useEffect(() => {
        if (shown === null || shown.finishedAt === null) {
            return;
        }

        setDraft(clientTextOf(shown) ?? "");
        // Tylko numer i koniec przebiegu: inaczej każdy krok i tyknięcie zegara nadpisywałyby
        // szkic poprawiany właśnie z ręki.
    }, [shown?.id, shown?.finishedAt]);

    /**
     * Description:
     * Uruchamia graf na zgłoszeniu z lewego panelu; nowy przebieg staje się pokazanym.
     *
     * Example args:
     *     action={ kind: "suggest", title: "Rozwiązanie", variant: "solution" }
     *
     * Example result:
     *     undefined — przebieg widać w konsoli, wynik w środkowym panelu
     */
    const runOnTicket = async (
        action: GraphAction,  // np. { kind: "search", title: "Rozpoznanie" }
    ) => {
        const body = action.kind === "suggest" ? { ...ticket, variant: action.variant } : ticket;

        setShownId(null);
        await start(action.kind, action.title, ticket.ticket_id, body, null);
    };

    /**
     * Description:
     * Uruchamia na szkicu dla klienta bramkę wysyłki albo „Popraw"; nowy przebieg staje się
     * pokazanym, więc wynik „Popraw" zastępuje szkic, a po bramce szkic zostaje ten sam.
     *
     * Example args:
     *     kind="polish"
     *
     * Example result:
     *     undefined — poprawiony tekst stoi w szkicu, przebieg w konsoli
     */
    const runOnDraft = async (
        kind: "gate_reply" | "polish",  // np. "gate_reply"
    ) => {
        const body  = kind === "gate_reply"
            ? { ticket_id: ticket.ticket_id, message: draft }
            : { ticket_id: ticket.ticket_id, text: draft };
        const title = kind === "gate_reply" ? "Sprawdź przed wysyłką" : "Popraw stylistycznie";

        setShownId(null);
        await start(kind, title, ticket.ticket_id, body, draft);
    };


    return (
        <div className="page">
            <TopBar instance={instance} totals={sessionTotals(runs, now)} running={running} />
            <GraphButtons variants={variants} ticket={ticket} disabled={running} onRun={runOnTicket} />
            <Columns>
                <TicketPanel ticket={ticket} onChange={setTicket} />
                <AnswerPanel
                    run={shown}
                    now={now}
                    draft={draft}
                    busy={running}
                    onDraftChange={setDraft}
                    onDraftRun={runOnDraft}
                />
                <ConsolePanel runs={runs} now={now} shownId={shown?.id ?? null} onShow={setShownId} />
            </Columns>
        </div>
    );
}

/**
 * Description:
 * Bieżąca chwila, odświeżana co `TICK_MS`, dopóki trwa przebieg; bez przebiegu stoi w miejscu,
 * więc strona się nie przerysowuje bez potrzeby.
 *
 * Example args:
 *     active=true
 *
 * Example result:
 *     1792483449123 — ms od epoki, rosnące co 200 ms
 */
function useNow(
    active: boolean,  // np. true, gdy trwa przebieg
): number {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        // --- bez przebiegu: jedna chwila na koniec, żeby czasy pokazały pełny przebieg ---
        if (!active) {
            setNow(Date.now());

            return;
        }

        const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);

        return () => window.clearInterval(timer);
    }, [active]);

    return now;
}
