/**
 * Description:
 * Belka u góry strony: nazwa, na czym stoi instancja (model generujący, model anonimizujący i stan
 * każdego materiału z `GET /instance`) oraz pod spodem siedem liczników przebiegów od otwarcia
 * strony. Dzięki niej widać, kto widzi zgłoszenie przed modelem i kto pisze odpowiedź, oraz czy
 * „nic nie znaleziono w instrukcjach" znaczy, że instrukcje milczą, czy że indeks jest pusty.
 *
 * Kto czyta: `pages/App.tsx` rysuje belkę jako pierwszą część strony; stan instancji i liczniki
 * dostaje od niego gotowe.
 *
 * | stan indeksu | pigułka          | znaczenie                                        |
 * |--------------|------------------|--------------------------------------------------|
 * | `built`      | zielona, liczba  | narzędzia na nim działają                        |
 * | `empty`      | żółta, „pusty"   | narzędzia oddają puste wyniki                    |
 * | `missing`    | czerwona, „brak" | narzędzia kończą się błędem konfiguracji         |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Wygląd idzie za szkicem układu z p. 77 (pigułki i małe karty liczników); kolory i odstępy
 *   stoją w `styles/app.css` pod klasami `top-bar`, `pill` i `stats`.
 * - Karta licznika krótko pulsuje na niebiesko, gdy zmienia się jej wartość, żeby było widać,
 *   co dał ostatni krok. Karta „Czas" w trakcie przebiegu tyka co 200 ms, więc zamiast krótkiego
 *   pulsu przy każdej zmianie pulsuje powoli przez cały przebieg.
 * - Pigułka anonimizacji pokazuje model bez organizacji z nazwy (`speakleash/`), pełną nazwę
 *   i silnik w dymku; niedostępna usługa ma kolor brakującego materiału.
 */

import { Tooltip } from "antd";
import { useEffect, useRef, useState } from "react";

import type { IndexItem, InstanceResponse } from "../../models/api/instance";
import type { Totals } from "../../models/runs/totals";
import { formatTokens } from "../../utils/count";
import { formatUsd } from "../../utils/currency";
import { formatDuration } from "../../utils/time";

// Nazwa indeksu dla człowieka; kolejność pigułek idzie za kolejnością z `GET /instance`.
const INDEX_LABELS: Record<IndexItem["index"], string> = {
    cards:     "karty zgłoszeń",
    threads:   "wątki zgłoszeń",
    sections:  "sekcje dokumentacji",
    fragments: "fragmenty dokumentacji",
    package:   "kod aplikacji",
};

/** Właściwości belki. */
interface TopBarProps {
    instance: InstanceResponse | null;  // null, dopóki `GET /instance` nie odpowie
    totals:   Totals;                   // liczniki całej sesji z sessionTotals()
    running:  boolean;                  // true, gdy trwa przebieg — karta „Czas" wolno pulsuje
}

/**
 * Description:
 * Belka: nazwa i pigułki w pierwszym wierszu, siedem kart liczników sesji w drugim.
 *
 * Example args:
 *     instance={ model: { provider: "openai", name: "gpt-6.1-sol" }, indexes: [ … ], … }
 *     totals={ costUsd: 0.1, llmCalls: 11, inputTokens: 1200, …, toolCalls: 16, runs: 3, … }
 *     running=false
 *
 * Example result:
 *     <header> z „Helpdesk AI by Tensoft" i pigułkami oraz <section> z kartami „Koszt LLM  0,100 USD"…
 */
export function TopBar({ instance, totals, running }: TopBarProps) {
    // Tokeny parami: nowe (in/out) i cache (read/write) — cztery klasy z `api`.
    const fresh  = `${formatTokens(totals.inputTokens)} / ${formatTokens(totals.outputTokens)}`;
    const cached = `${formatTokens(totals.cacheReadTokens)} / ${formatTokens(totals.cacheWriteTokens)}`;

    // Kolejność kart: najpierw to, co interesuje na pokazie (koszt, czas), potem szczegóły.
    // Czas zmienia się w trakcie przebiegu co 200 ms, więc zamiast pulsu przy zmianie pulsuje
    // powoli przez cały przebieg.
    const stats = [
        { title: "Koszt LLM",                 value: formatUsd(totals.costUsd),          pulse: true,  live: false },
        { title: "Czas",                      value: formatDuration(totals.durationMs),  pulse: false, live: running },
        { title: "Przebiegi",                 value: String(totals.runs),                pulse: true,  live: false },
        { title: "Wywołania narzędzi",        value: String(totals.toolCalls),           pulse: true,  live: false },
        { title: "Wywołania modelu",          value: String(totals.llmCalls),            pulse: true,  live: false },
        { title: "Tokeny nowe (in/out)",      value: fresh,                              pulse: true,  live: false },
        { title: "Tokeny cache (read/write)", value: cached,                             pulse: true,  live: false },
    ];

    return (
        <>
            <header className="top-bar">
                <h1>Helpdesk AI <span className="top-bar-by">by Tensoft</span></h1>
                <div className="pills">
                    <span className="muted pills-label">Modele:</span>
                    <ModelPill instance={instance} />
                    <AnonymizationPill instance={instance} />
                    <Materials instance={instance} />
                </div>
            </header>
            <section className="stats" aria-label="Statystyki sesji">
                {stats.map((stat) => <StatCard key={stat.title} {...stat} />)}
            </section>
        </>
    );
}

/**
 * Description:
 * Pigułka modelu generującego; przy atrapie napis „atrapa", bo nazwa z `.env` atrapy nie
 * dotyczy. W dymku dostawca.
 *
 * Example args:
 *     instance={ model: { provider: "fake", name: null }, … }
 *
 * Example result:
 *     <span className="pill">generacja: atrapa</span>
 */
function ModelPill({ instance }: { instance: InstanceResponse | null }) {
    const model = instance?.model;
    const label = model === undefined ? "…" : model.name === null ? "atrapa" : model.name;

    return (
        <Tooltip title={model === undefined ? null : `model generujący · dostawca ${model.provider}`}>
            <span className="pill">generacja: {label}</span>
        </Tooltip>
    );
}

/**
 * Description:
 * Pigułka modelu anonimizującego: model bez organizacji z nazwy, „atrapa" przy atrapie silnika
 * albo „niedostępna", gdy usługa nie odpowiada; w dymku pełna nazwa modelu i silnik.
 *
 * Example args:
 *     instance={ anonymization: { state: "available", engine: "agent",
 *                                 model: "speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic" }, … }
 *
 * Example result:
 *     <span className="pill">anonimizacja: Bielik-11B-v3.0-Instruct-FP8-Dynamic</span>
 */
function AnonymizationPill({ instance }: { instance: InstanceResponse | null }) {
    const info = instance?.anonymization;

    // --- stan instancji jeszcze nie przyszedł ---
    if (info === undefined) {
        return <span className="pill">anonimizacja: …</span>;
    }

    // --- usługa nie odpowiada: przebiegi grafów skończą się błędem ---
    if (info.state === "unavailable") {
        return <span className="pill" data-state="missing">anonimizacja: niedostępna</span>;
    }

    const label = info.model === null ? "atrapa" : info.model.split("/").at(-1);
    const hint  = info.model === null
        ? `model anonimizujący · silnik ${info.engine}, bez modelu`
        : `model anonimizujący ${info.model} · silnik ${info.engine}`;

    return (
        <Tooltip title={hint}>
            <span className="pill">anonimizacja: {label}</span>
        </Tooltip>
    );
}

/** Właściwości karty licznika. */
interface StatCardProps {
    title: string;   // np. "Koszt LLM"
    value: string;   // np. "0,100 USD"
    pulse: boolean;  // czy karta pulsuje przy zmianie wartości
    live:  boolean;  // czy karta pulsuje powoli bez przerwy — „Czas" w trakcie przebiegu
}

/**
 * Description:
 * Karta licznika: etykieta po lewej, liczba po prawej; przy zmianie wartości krótko pulsuje,
 * a karta „na żywo" pulsuje powoli bez przerwy.
 * Pulsowanie restartuje się na zmianę dwiema nazwami animacji (`data-flash` 1 i 2), bo ta sama
 * nazwa nie rusza animacji od nowa; przy pierwszym rysowaniu karta nie pulsuje.
 *
 * Example args:
 *     title="Wywołania modelu"
 *     value="11"
 *     pulse=true
 *     live=false
 *
 * Example result:
 *     <div className="stat" data-flash="1"> z „Wywołania modelu" i „11"
 */
function StatCard({ title, value, pulse, live }: StatCardProps) {
    // Która z dwóch animacji pulsu trwa: 0 — żadna, 1 i 2 na zmianę przy każdej zmianie wartości.
    const [flash, setFlash] = useState(0);
    // Wartość z poprzedniego rysowania; pierwsze rysowanie nie jest zmianą.
    const previous          = useRef(value);

    useEffect(() => {
        // --- wartość bez zmian albo karta, która nie pulsuje ---
        if (!pulse || value === previous.current) {
            return;
        }

        previous.current = value;
        setFlash((current) => (current === 1 ? 2 : 1));
    }, [value, pulse]);

    return (
        <div className="stat" data-flash={flash} data-live={live}>
            <span className="stat-label">{title}</span>
            <span className="stat-value">{value}</span>
        </div>
    );
}

/**
 * Description:
 * Pigułki materiałów: nazwa indeksu i liczba elementów albo „pusty" czy „brak"; przy paczce kodu
 * dymek z gałęzią i dniem budowy.
 *
 * Example args:
 *     instance={ indexes: [{ material: "docs", index: "sections", state: "empty", count: 0 }], … }
 *
 * Example result:
 *     <span className="pill" data-state="empty">sekcje dokumentacji · pusty</span>
 */
function Materials({ instance }: { instance: InstanceResponse | null }) {
    // --- stan instancji jeszcze nie przyszedł albo nie przyszedł wcale ---
    if (instance === null) {
        return null;
    }

    const branch = instance.code_package === null
        ? "paczki kodu nie ma"
        : `gałąź ${instance.code_package.branch ?? "nieznana"}, zbudowana ${instance.code_package.built_on}`;

    return (
        <>
            <span className="muted pills-label">Materiały:</span>
            {instance.indexes.map((item) => {
                const state = item.state === "built" ? String(item.count) : item.state === "empty" ? "pusty" : "brak";
                const pill  = (
                    <span key={item.index} className="pill" data-state={item.state}>
                        {INDEX_LABELS[item.index]} · {state}
                    </span>
                );

                return item.index === "package" ? <Tooltip key={item.index} title={branch}>{pill}</Tooltip> : pill;
            })}
        </>
    );
}
