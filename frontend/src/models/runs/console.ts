/**
 * Description:
 * Wiersze konsoli przebiegu i treść dialogu szczegółów — model frontu. Składa je
 * `runs/rows.ts` z kroków przebiegu, a rysują `ConsolePanel` i `StepDialog`.
 *
 * | model           | co opisuje                                             |
 * |-----------------|--------------------------------------------------------|
 * | `ConsoleRow`    | jeden wiersz: krok, wywołanie narzędzia albo krok w toku |
 * | `StepDetail`    | treść dialogu po kliknięciu wiersza                    |
 * | `DetailSection` | jedna część dialogu: nagłówek, dopisek, treść          |
 */

/** Rodzaj wiersza konsoli; od niego zależy wygląd wiersza. */
export type RowKind = "anonymize" | "turn" | "tool" | "respond" | "other" | "pending";

/** Jedna część dialogu szczegółów: nagłówek, dopisek i treść w czcionce stałej szerokości. */
export interface DetailSection {
    heading: string;  // np. "Zapytanie"
    note:    string;  // np. "to, co dostał model · 214 zn."
    body:    string;  // np. '{\n  "problem": "…"\n}'
}

/** Treść dialogu szczegółów jednego wiersza. */
export interface StepDetail {
    title:    string;  // np. "find_tickets_vector · tura 1"
    meta:     string;  // np. "start 00:03.0 · 412 ms"
    sections: DetailSection[];
}

/** Jeden wiersz konsoli przebiegu. */
export interface ConsoleRow {
    key:      string;             // np. "3-2-call_1"
    kind:     RowKind;
    start:    string;             // np. "00:03.0"
    label:    string;             // np. "agent · tura 1"
    summary:  string;             // np. "błąd"; pusty w turze i w udanym wywołaniu
    cost:     string;             // np. "0,004 USD"; pusty poza turą modelu
    duration: string;             // np. "2,1 s"
    detail:   StepDetail | null;  // null w wierszu w toku
}
