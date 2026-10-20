/**
 * Description:
 * Części wspólne odpowiedzi tras `api`: zużycie modelu, wpis logu, źródło i błąd — przepisane
 * z `api/app/entry_routers/models.py`. Nazwy pól jak w `api` (snake_case), bo JSON przychodzi
 * bez przeróbki.
 *
 * | model           | gdzie przychodzi                                        |
 * |-----------------|---------------------------------------------------------|
 * | `UsageItem`     | w każdej odpowiedzi trasy grafu i w kroku tury modelu   |
 * | `LogItem`       | w każdej odpowiedzi trasy grafu                         |
 * | `SourceItem`    | w odpowiedzi `/search` i `/suggest`                     |
 * | `ErrorResponse` | przy statusie 503 i w zdarzeniu `error` strumienia      |
 *
 * Kto czyta:
 * - `UsageItem` — `runs/totals.ts` (liczniki belki i przebiegu) i `runs/rows.ts` (koszt
 *   i tokeny tury modelu w konsoli).
 * - `SourceItem` — zakładka „Źródła" w `pages/panels/AnswerPanel.tsx`.
 * - `ErrorResponse` — `api/client.ts`, który zamienia go na `ApiError` z opisem dla człowieka.
 * - `LogItem` przychodzi w każdej odpowiedzi, ale front go nie pokazuje: przebieg widać
 *   w krokach strumienia (`step.ts`).
 */

/** Zużycie modelu w przebiegu albo w jednej turze: wywołania, cztery klasy tokenów i koszt. */
export interface UsageItem {
    llm_calls:          number;  // np. 3
    prompt_tokens:      number;  // np. 18200 — świeże wejście
    completion_tokens:  number;  // np. 940
    cache_write_tokens: number;  // np. 0
    cache_read_tokens:  number;  // np. 12400
    cost_usd:           number;  // np. 0.0916
}

/** Wpis logu przebiegu: węzeł i tekst dla człowieka, bez treści zgłoszenia. */
export interface LogItem {
    node:    string;  // np. "agent"
    message: string;  // np. "tura 1: narzędzia: find_tickets_vector; 0,0041 USD"
}

/** Materiał, który agent odczytał: zgłoszenie, sekcja instrukcji albo zacytowany fragment kodu. */
export interface SourceItem {
    source:  string;         // np. "tickets", "docs", "code"
    item_id: string;         // np. "33644"
    title:   string;         // np. "Wysyłka przez ePUAP kończy się błędem"
    date:    string | null;  // np. "2026-03-14"; kod nie ma daty
}

/** Odpowiedź błędu: statusu 503 albo zdarzenia `error` strumienia. */
export interface ErrorResponse {
    detail:     string;         // np. "Usługa chwilowo niedostępna"
    request_id: string | null;  // np. "6f1c…"
}
