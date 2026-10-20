/**
 * Description:
 * Błąd rozmowy z usługą `api`, jeden na wszystkie drogi, którymi błąd przychodzi: status inny
 * niż 2xx, zdarzenie `error` w strumieniu, strumień urwany bez wyniku i brak odpowiedzi.
 *
 * Kto czyta: `api/client.ts` go zgłasza, a `runs/useRuns.ts` łapie i zapisuje jego opis
 * w przebiegu; środkowy panel pokazuje ten opis w zakładce „Dla wdrożeniowca", a `pages/App.tsx`
 * w komunikacie, gdy nie przyjdzie stan instancji albo lista wariantów.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Opis jest dla człowieka i nie cytuje treści zgłoszenia: `api` jej w błędach nie podaje.
 * - Inny wyjątek niż ten to usterka frontu, nie `api` — `useRuns()` opisuje go osobno.
 */

/**
 * Description:
 * Błąd rozmowy z `api` z opisem, który można pokazać człowiekowi, i identyfikatorem żądania,
 * po którym znajdzie się wpisy w logu usługi.
 *
 * Example args:
 *     message="anonimizator nie odpowiedział"
 *     requestId="6f1c…"
 *
 * Example result:
 *     ApiError z `message` i `requestId`
 */
export class ApiError extends Error {
    readonly requestId: string | null;

    constructor(
        message:   string,         // np. "Usługa chwilowo niedostępna"
        requestId: string | null,  // np. "6f1c…"
    ) {
        super(message);

        this.name      = "ApiError";
        this.requestId = requestId;
    }
}
