/**
 * Description:
 * Jedyne miejsce frontu, które zna trasy `api`: odczyt stanu instancji i wariantów oraz przebieg
 * grafu strumieniem. Komponenty wołają te funkcje i nie składają adresów same.
 *
 * | funkcja         | trasa                                   | co oddaje                    |
 * |-----------------|-----------------------------------------|------------------------------|
 * | `getInstance()` | `GET /instance`                         | model i stan indeksów        |
 * | `getVariants()` | `GET /variants`                         | warianty do guzików          |
 * | `runGraph()`    | `POST` trasy grafu, `text/event-stream` | kroki po drodze, wynik na końcu |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Front woła `api` pod przedrostkiem `/api`, który zdejmuje proxy (Vite w dev, nginx na prod),
 *   więc przeglądarka rozmawia z jednym adresem i `api` nie potrzebuje CORS.
 * - Błąd przychodzi trzema drogami: status inny niż 2xx przed strumieniem (422 walidacji,
 *   500 konfiguracji), zdarzenie `error` w strumieniu (awaria zależności) albo strumień urwany
 *   bez wyniku (błąd konfiguracji w trakcie). Każda kończy się `ApiError` z opisem dla człowieka.
 */

import { ApiError } from "../errors/ApiError";
import type { ErrorResponse } from "../models/api/common";
import type { GraphKind, GraphOutcome } from "../models/runs/graph";
import type { InstanceResponse } from "../models/api/instance";
import type { StepItem } from "../models/api/step";
import type { VariantsResponse } from "../models/api/suggest";
import { readEvents } from "./sse";

// Przedrostek tras `api` po stronie frontu; ten sam zdejmują proxy Vite i nginx.
const API_PREFIX = "/api";

// Trasa każdego grafu; `suggest` dostaje wariant w treści żądania, nie w ścieżce.
const GRAPH_PATHS: Record<GraphKind, string> = {
    search:       "/search",
    suggest:      "/suggest",
    parse_ticket: "/parse-ticket",
    gate_close:   "/gate/close",
    gate_reply:   "/gate/reply",
    polish:       "/polish",
};

/**
 * Description:
 * Odczytuje stan instancji: model generujący, stan indeksów i gałąź paczki kodu.
 *
 * Example args:
 *     (brak)
 *
 * Example result:
 *     { model: { provider: "openai", name: "gpt-6.1-sol" }, indexes: [ … ], code_package: { … } }
 *
 * Raises:
 *     ApiError: `api` odpowiedziała błędem albo nie odpowiedziała
 */
export async function getInstance(): Promise<InstanceResponse> {
    return getJson<InstanceResponse>("/instance");
}

/**
 * Description:
 * Odczytuje warianty odpowiedzi z rejestru grafów — z nich front rysuje guziki.
 *
 * Example args:
 *     (brak)
 *
 * Example result:
 *     { variants: [{ name: "questions", label: "Jakie pytania zadać", requires_hits: false }, …] }
 *
 * Raises:
 *     ApiError: `api` odpowiedziała błędem albo nie odpowiedziała
 */
export async function getVariants(): Promise<VariantsResponse> {
    return getJson<VariantsResponse>("/variants");
}

/**
 * Description:
 * Uruchamia graf strumieniem: każdy krok oddaje od razu przez `onStep`, a po ostatnim oddaje
 * wynik razem z rodzajem grafu, który go dał.
 *
 * Example args:
 *     kind="search"
 *     body={ ticket_id: "90101", body: "Od wczoraj…", … }
 *     onStep=(step) => …
 *
 * Example result:
 *     { kind: "search", result: { sources: [ … ], internal_notes: "## …", … } }
 *
 * Raises:
 *     ApiError: status inny niż 2xx, zdarzenie `error` albo strumień urwany bez wyniku
 */
export async function runGraph<K extends GraphKind>(
    kind:   K,                         // np. "search"
    body:   object,                    // np. { ticket_id: "90101", body: "…" }
    onStep: (step: StepItem) => void,  // np. (step) => setSteps(…)
): Promise<Extract<GraphOutcome, { kind: K }>> {
    // --- żądanie: ta sama trasa co JSON, strumień wybiera nagłówek ---
    const response = await send(`${API_PREFIX}${GRAPH_PATHS[kind]}`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body:    JSON.stringify(body),
    });

    // --- błąd przed strumieniem: walidacja (422) albo konfiguracja (500) ---
    if (!response.ok || response.body === null) {
        throw await failureOf(response);
    }

    // --- kroki po drodze, wynik albo błąd na końcu ---
    for await (const event of readEvents(response.body)) {
        if (event.event === "step") {
            onStep(JSON.parse(event.data) as StepItem);
        }

        if (event.event === "result") {
            return { kind, result: JSON.parse(event.data) } as Extract<GraphOutcome, { kind: K }>;
        }

        if (event.event === "error") {
            const error = JSON.parse(event.data) as ErrorResponse;

            throw new ApiError(error.detail, error.request_id);
        }
    }

    // --- strumień skończył się bez wyniku: błąd konfiguracji zerwał go w trakcie ---
    throw new ApiError("przebieg urwał się bez wyniku — szczegóły w logu usługi api", null);
}

/**
 * Description:
 * Odczytuje JSON z trasy `GET`; status inny niż 2xx kończy się błędem z opisem z odpowiedzi.
 *
 * Example args:
 *     path="/instance"
 *
 * Example result:
 *     { model: { … }, indexes: [ … ], code_package: null }
 *
 * Raises:
 *     ApiError: `api` odpowiedziała błędem albo nie odpowiedziała
 */
async function getJson<T>(
    path: string,  // np. "/instance"
): Promise<T> {
    const response = await send(`${API_PREFIX}${path}`, { headers: { Accept: "application/json" } });

    if (!response.ok) {
        throw await failureOf(response);
    }

    return (await response.json()) as T;
}

/**
 * Description:
 * Wysyła żądanie; brak odpowiedzi (sieć, wyłączony kontener) zamienia na `ApiError`, żeby
 * wołający łapał jeden rodzaj błędu.
 *
 * Example args:
 *     url="/api/instance"
 *     init={ headers: { Accept: "application/json" } }
 *
 * Example result:
 *     Response z fetch
 *
 * Raises:
 *     ApiError: żądanie nie dostało żadnej odpowiedzi
 */
async function send(
    url:  string,       // np. "/api/instance"
    init: RequestInit,  // np. { method: "POST", body: "…" }
): Promise<Response> {
    try {
        return await fetch(url, init);
    } catch {
        // fetch rzuca TypeError bez odpowiedzi; jego tekst zależy od przeglądarki i nic nie mówi.
        throw new ApiError("brak odpowiedzi od api — czy usługa działa?", null);
    }
}

/**
 * Description:
 * Opis błędu z odpowiedzi `api`: `detail` z `ErrorResponse` (503), lista błędów walidacji
 * FastAPI (422) albo sam status, gdy treść nie jest JSON-em (500 bez obsługi, proxy).
 *
 * Example args:
 *     response=Response(status=422, body='{"detail": [{"loc": ["body", "body"], "msg": "Field required"}]}')
 *
 * Example result:
 *     ApiError("422: body.body: Field required", null)
 */
async function failureOf(
    response: Response,  // np. odpowiedź ze statusem 503
): Promise<ApiError> {
    const requestId = response.headers.get("X-Request-ID");
    const text      = await response.text();

    try {
        const body = JSON.parse(text) as { detail?: unknown };

        // --- 503 i obsłużone błędy: jeden opis w `detail` ---
        if (typeof body.detail === "string") {
            return new ApiError(`${response.status}: ${body.detail}`, requestId);
        }

        // --- 422 walidacji FastAPI: lista błędów pól ---
        if (Array.isArray(body.detail)) {
            const fields = body.detail.map((item: { loc?: unknown[]; msg?: string }) =>
                `${(item.loc ?? []).join(".")}: ${item.msg ?? ""}`);

            return new ApiError(`${response.status}: ${fields.join("; ")}`, requestId);
        }
    } catch {
        // Treść nie jest JSON-em: zostaje sam status, niżej.
    }

    return new ApiError(`${response.status}: ${response.statusText || "błąd api"}`, requestId);
}
