/**
 * Description:
 * Środkowy panel: odpowiedź pokazanego przebiegu — ostatniego albo wczytanego z konsoli —
 * w czterech zakładkach: „Dla klienta" (szkic do wysłania), „Dla wdrożeniowca" (uwagi, werdykt
 * albo karta), „Źródła" (to, co agent odczytał) i „Po anonimizacji" (tekst, który dostał model).
 * Nagłówek mówi, który przebieg widać i ile kosztował.
 *
 * Kto czyta: `pages/App.tsx` podaje pokazany przebieg i szkic; zakładki rysują `ClientTab.tsx`
 * i `NotesTab.tsx`, a listę źródeł i tekst po anonimizacji ten plik.
 *
 * | stan przebiegu        | panel pokazuje ZAMIAST zakładek                             |
 * |-----------------------|-------------------------------------------------------------|
 * | żadnego jeszcze nie ma | ramkę „Nic jeszcze nie uruchomiono"                        |
 * | trwa                  | ramkę „Przebieg w toku" z tym, co trwa, i tekst po anonimizacji |
 * | zakończony błędem     | ramkę z opisem błędu i tekst po anonimizacji, jeśli doszedł |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Zakładki widać tylko przy przebiegu, który dał wynik; stan bez wyniku stoi w ramce zamiast
 *   nich, żeby było go widać od razu, a nie dopiero w jednej z zakładek.
 * - Zakładka na start zależy od grafu: propozycja odpowiedzi i „Popraw" otwierają „Dla
 *   klienta", reszta „Dla wdrożeniowca". Zakładki przebudowują się przy innym przebiegu (klucz
 *   to numer przebiegu).
 * - Szkic trzyma `pages/App.tsx` i bierze go z pokazanego przebiegu; przebieg bez tekstu dla
 *   klienta daje pusty szkic.
 */

import { Alert, Empty, List, Space, Tabs, Tag, Typography } from "antd";

import type { SourceItem } from "../../models/api/common";
import type { GraphOutcome } from "../../models/runs/graph";
import type { Run } from "../../models/runs/run";
import { anonymizedTextOf, sourcesOf } from "../../runs/answer";
import { pendingLabel, runSummary } from "../../runs/rows";
import { ClientTab } from "./ClientTab";
import { NotesTab } from "./NotesTab";

// Nazwa rodzaju źródła dla człowieka; kod jest źródłem tylko jako zacytowana przyczyna.
const SOURCE_LABELS: Record<string, string> = {
    tickets: "zgłoszenie",
    docs:    "instrukcja",
    code:    "kod · przyczyna",
};

// Podpowiedź przed pierwszym przebiegiem: gdzie kliknąć i gdzie co się pojawi.
const NO_RUN_HINT = "Wybierz guzik nad kolumnami: odpowiedź pojawi się tutaj, a kroki przebiegu w konsoli po prawej.";

/** Właściwości środkowego panelu. */
interface AnswerPanelProps {
    run:           Run | null;                                // pokazany przebieg; null przed pierwszym
    now:           number;                                    // Date.now() — czas przebiegu w toku
    draft:         string;                                    // szkic dla klienta
    busy:          boolean;                                   // true, gdy trwa przebieg
    onDraftChange: (draft: string) => void;                   // np. setDraft
    onDraftRun:    (kind: "gate_reply" | "polish") => void;   // np. runOnDraft
}

/**
 * Description:
 * Panel odpowiedzi: nagłówek przebiegu, a pod nim ramka stanu (przed pierwszym przebiegiem,
 * w toku, po błędzie) albo cztery zakładki wyniku.
 *
 * Example args:
 *     run=Run(kind="suggest", title="Gotowa odpowiedź", outcome={ … })
 *     now=Date.now()
 *     draft="Dzień dobry, …"
 *     busy=false
 *     onDraftChange=setDraft
 *     onDraftRun=runOnDraft
 *
 * Example result:
 *     <section className="column"> z „Gotowa odpowiedź · zgłoszenie 90101" i zakładkami
 */
export function AnswerPanel({ run, now, draft, busy, onDraftChange, onDraftRun }: AnswerPanelProps) {
    const title = run === null ? "Odpowiedź" : `${run.title} · zgłoszenie ${run.ticketId || "bez numeru"}`;

    return (
        <section className="column column-answer" aria-label="Odpowiedź">
            <div className="column-header">
                <h2>{title}</h2>
                {run !== null && <span className="muted">{runSummary(run, now)}</span>}
            </div>
            <AnswerBody run={run} draft={draft} busy={busy} onDraftChange={onDraftChange} onDraftRun={onDraftRun} />
        </section>
    );
}

/** Właściwości treści panelu: te same co panelu, bez zegara. */
type AnswerBodyProps = Omit<AnswerPanelProps, "now">;

/**
 * Description:
 * Treść panelu pod nagłówkiem: ramka stanu albo zakładki wyniku, zależnie od przebiegu.
 *
 * Example args:
 *     run=Run(finishedAt=null, steps=[anonymize, agent])
 *     draft=""
 *     busy=true
 *     onDraftChange=setDraft
 *     onDraftRun=runOnDraft
 *
 * Example result:
 *     <Space> z ramką „Przebieg w toku · ↳ find_tickets_vector" i tekstem po anonimizacji
 */
function AnswerBody({ run, draft, busy, onDraftChange, onDraftRun }: AnswerBodyProps) {
    // --- przed pierwszym przebiegiem: informacja zamiast zakładek ---
    if (run === null) {
        return <Alert type="info" showIcon title="Nic jeszcze nie uruchomiono" description={NO_RUN_HINT} />;
    }

    const anonymized = anonymizedTextOf(run);

    // --- przebieg trwa: co trwa teraz, a pod spodem tekst, który dostał model ---
    if (run.finishedAt === null) {
        return (
            <Space orientation="vertical" size={14} style={{ width: "100%" }}>
                <Alert
                    type="info"
                    showIcon
                    title={<><span className="live-dot" aria-hidden="true" />Przebieg w toku · {pendingLabel(run.steps)}</>}
                    description="Odpowiedź pojawi się tutaj po ostatnim kroku; kroki widać na żywo w konsoli po prawej."
                />
                {anonymized !== null && <AnonymizedText text={anonymized} />}
            </Space>
        );
    }

    // --- przebieg zakończony błędem: opis z `api` albo usterka frontu zamiast zakładek ---
    if (run.error !== null || run.outcome === null) {
        return (
            <Space orientation="vertical" size={14} style={{ width: "100%" }}>
                <Alert type="error" showIcon title="Przebieg zakończony błędem" description={run.error} />
                {anonymized !== null && <AnonymizedText text={anonymized} />}
            </Space>
        );
    }

    return (
        <AnswerTabs
            run={run}
            outcome={run.outcome}
            draft={draft}
            busy={busy}
            onDraftChange={onDraftChange}
            onDraftRun={onDraftRun}
        />
    );
}

/** Właściwości zakładek: przebieg z wynikiem i ten wynik osobno, żeby nie sprawdzać go drugi raz. */
type AnswerTabsProps = Omit<AnswerBodyProps, "run"> & { run: Run; outcome: GraphOutcome };

/**
 * Description:
 * Cztery zakładki wyniku przebiegu; zakładka na start zależy od grafu.
 *
 * Example args:
 *     run=Run(kind="gate_close", …)
 *     outcome={ kind: "gate_close", result: { verdict: "block", … } }
 *     draft=""
 *     busy=false
 *     onDraftChange=setDraft
 *     onDraftRun=runOnDraft
 *
 * Example result:
 *     <Tabs> z „Dla klienta", „Dla wdrożeniowca" (otwarta na start), „Źródła · 0"
 *     i „Po anonimizacji"
 */
function AnswerTabs({ run, outcome, draft, busy, onDraftChange, onDraftRun }: AnswerTabsProps) {
    const sources    = sourcesOf(run);
    const anonymized = anonymizedTextOf(run);

    const tabs = [
        {
            key:      "client",
            label:    "Dla klienta",
            children: (
                <ClientTab
                    draft={draft}
                    run={run}
                    busy={busy}
                    onChange={onDraftChange}
                    onCheck={() => onDraftRun("gate_reply")}
                    onPolish={() => onDraftRun("polish")}
                />
            ),
        },
        { key: "notes",   label: "Dla wdrożeniowca",           children: <NotesTab outcome={outcome} /> },
        { key: "sources", label: `Źródła · ${sources.length}`, children: <SourceList sources={sources} /> },
        {
            key:      "anonymized",
            label:    "Po anonimizacji",
            children: anonymized === null
                ? <Empty description="Strumień nie przyniósł tekstu po anonimizacji." />
                : <AnonymizedText text={anonymized} />,
        },
    ];

    return <Tabs key={run.id} defaultActiveKey={startTab(outcome)} items={tabs} />;
}

/**
 * Description:
 * Zakładka na start dla wyniku: tekst dla klienta po propozycji i „Popraw", uwagi po reszcie.
 *
 * Example args:
 *     outcome={ kind: "gate_reply", result: { … } }
 *
 * Example result:
 *     "notes"
 */
function startTab(
    outcome: GraphOutcome,  // wynik pokazanego przebiegu
): string {
    if (outcome.kind === "suggest" || outcome.kind === "polish") {
        return "client";
    }

    return "notes";
}

/**
 * Description:
 * Tekst zgłoszenia po anonimizacji: dokładnie to, co dostał model, ze znacznikami w miejscu
 * danych osobowych.
 *
 * Example args:
 *     text="{IMIĘ} {NAZWISKO} z UG Zalesie zgłasza, że przesyłki nie przychodzą."
 *
 * Example result:
 *     <Space> z nagłówkiem „Tekst po anonimizacji" i tekstem w bloku
 */
function AnonymizedText({ text }: { text: string }) {
    return (
        <Space orientation="vertical" size={6} style={{ width: "100%" }}>
            <Space size={8} align="baseline">
                <Typography.Text strong>Tekst po anonimizacji</Typography.Text>
                <span className="muted">to, co dostał model · {text.length} zn.</span>
            </Space>
            <pre className="code-block">{text}</pre>
        </Space>
    );
}

/**
 * Description:
 * Lista źródeł: rodzaj, identyfikator, tytuł i data; bez źródeł — wyjaśnienie, czemu ich nie ma.
 *
 * Example args:
 *     sources=[{ source: "code", item_id: "src/lib/Pobieranie.class.php:41-48", title: "…", date: null }]
 *
 * Example result:
 *     <List> z wierszem „kod · przyczyna  src/lib/Pobieranie.class.php:41-48  …"
 */
function SourceList({ sources }: { sources: SourceItem[] }) {
    // --- brak źródeł to informacja, nie brak danych ---
    if (sources.length === 0) {
        return (
            <Empty
                description="Brak źródeł: agent niczego nie odczytał albo ten graf nie czyta materiału."
            />
        );
    }

    return (
        <List
            dataSource={sources}
            renderItem={(source) => (
                <List.Item>
                    <Space orientation="vertical" size={2}>
                        <Space size={8} wrap>
                            <Tag>{SOURCE_LABELS[source.source] ?? source.source}</Tag>
                            <span className="mono">{source.item_id}</span>
                            {source.date !== null && <span className="muted">{source.date}</span>}
                        </Space>
                        <Typography.Text>{source.title}</Typography.Text>
                    </Space>
                </List.Item>
            )}
        />
    );
}
