/**
 * Description:
 * Zakładka „Dla wdrożeniowca": to, czego klient nie dostaje, a co wdrożeniowiec ma przeczytać
 * przed odpowiedzią. Co tu stoi, zależy od grafu, który dał wynik.
 *
 * | graf                       | zakładka pokazuje                                        |
 * |----------------------------|----------------------------------------------------------|
 * | `search`, `suggest`        | uwagi dla wdrożeniowca (Markdown: `##` i listy)          |
 * | `gate_close`, `gate_reply` | werdykt z zestawem reguł, powody, co dopisać             |
 * | `parse_ticket`             | kartę zgłoszenia pole po polu                            |
 * | `polish`                   | informację, że poprawiony tekst stoi w „Dla klienta"     |
 *
 * Kto czyta: `AnswerPanel.tsx` rysuje zakładkę dla wyniku pokazanego przebiegu.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Wynik rozpoznaje się po `outcome.kind` (`models/runs/graph.ts`); nowy graf z guzikiem to nowy
 *   przypadek tutaj, a kompilator wskaże brak.
 * - Zakładka dostaje sam wynik: przebieg w toku, zakończony błędem i stan przed pierwszym
 *   przebiegiem pokazuje `AnswerPanel.tsx` zamiast zakładek.
 * - Werdykt bramki ma u góry jedną ramkę: czy blokuje, czy przepuszcza, i który zestaw reguł
 *   go wydał. Powody i to, co dopisać, stoją pod nią jako zwykłe sekcje, jednakowe.
 */

import { Alert, Descriptions, Empty, List, Space, Tag, Typography } from "antd";
import Markdown from "react-markdown";

import type { VerdictResponse } from "../../models/api/gate";
import type { TicketCard } from "../../models/api/parseTicket";
import type { GraphOutcome } from "../../models/runs/graph";
import { linesAsParagraphs } from "../../utils/markdown";

// Pola karty z treścią sprawy; numer, data, zużycie i log stoją gdzie indziej albo nigdzie.
type CardField = Exclude<keyof TicketCard, "ticket_id" | "date" | "usage" | "log">;

// Pola karty w kolejności z kontraktu sparsowanego zgłoszenia: nazwa dla człowieka i pole.
const CARD_FIELDS: { label: string; field: CardField }[] = [
    { label: "Komponent",           field: "component" },
    { label: "Problem",             field: "problem" },
    { label: "Objawy",              field: "symptoms" },
    { label: "Kody błędów",         field: "error_codes" },
    { label: "Przyczyna",           field: "cause" },
    { label: "Rozwiązanie",         field: "solution" },
    { label: "Rozstrzygnięcie",     field: "resolution" },
    { label: "Pytania konsultanta", field: "questions_summary" },
];

/**
 * Description:
 * Zakładka dla wyniku przebiegu, w kształcie zależnym od grafu.
 *
 * Example args:
 *     outcome={ kind: "gate_close", result: { verdict: "block", … } }
 *
 * Example result:
 *     <VerdictView> z werdyktem bramki zamknięcia
 */
export function NotesTab({ outcome }: { outcome: GraphOutcome }) {
    switch (outcome.kind) {
        // --- rozpoznanie: same uwagi ---
        case "search":
            return <NotesView notes={outcome.result.internal_notes} />;

        // --- propozycja: uwagi i informacja, gdy treści dla klienta nie ma ---
        case "suggest":
            return (
                <Space orientation="vertical" size={10} style={{ width: "100%" }}>
                    {outcome.result.text === null && (
                        <Alert type="info" showIcon title="Bez propozycji dla klienta — powód w uwagach poniżej." />
                    )}
                    <NotesView notes={outcome.result.internal_notes} />
                </Space>
            );

        // --- bramki: werdykt w jednym kształcie ---
        case "gate_close":
        case "gate_reply":
            return <VerdictView verdict={outcome.result} />;

        // --- karta zgłoszenia ---
        case "parse_ticket":
            return <CardView card={outcome.result} />;

        // --- „Popraw" uwag nie ma ---
        case "polish":
            return (
                <Typography.Paragraph type="secondary">
                    „Popraw stylistycznie” nie ma uwag: poprawiony tekst stoi w zakładce „Dla klienta”.
                </Typography.Paragraph>
            );
    }
}

/**
 * Description:
 * Uwagi dla wdrożeniowca w lekkim Markdownie (nagłówki `##` i listy `-`), każda zwykła linia
 * jako osobny akapit; puste uwagi to informacja, że ich nie ma.
 *
 * Example args:
 *     notes="## Zgłoszenia historyczne\n- 90001: wstrzymana pozycja…"
 *
 * Example result:
 *     <div className="notes"> z nagłówkiem i listą
 */
function NotesView({ notes }: { notes: string }) {
    if (notes.trim() === "") {
        return <Empty description="Bez uwag dla wdrożeniowca." />;
    }

    // Każda zwykła linia to osobny akapit z odstępem: uwagi propozycji to notatki w kolejnych
    // liniach („Ad. 1. …"), które Markdown skleiłby w jeden blok tekstu.
    return <div className="notes"><Markdown>{linesAsParagraphs(notes)}</Markdown></div>;
}

/**
 * Description:
 * Werdykt bramki: u góry ramka z rozstrzygnięciem i zestawem reguł, który je wydał, pod nią
 * powody i wskazówki, co poprawić — jednakowymi sekcjami. Tego, że werdykt da się obejść, zakładka nie
 * powtarza: to kontrakt z helpdeskiem (`overridable`), a nie informacja dla oglądającego pokaz.
 *
 * Example args:
 *     verdict={ verdict: "block", reasons: ["Nie widać, co zrobiono."],
 *               hint: "Dopisz, co zrobiono.", rules_version: 1, … }
 *
 * Example result:
 *     <Space> z ramką „Blokuje — zestaw reguł nr 1" i sekcjami „Dlaczego" i „Wskazówki"
 */
function VerdictView({ verdict }: { verdict: VerdictResponse }) {
    const blocks = verdict.verdict === "block";

    return (
        <Space orientation="vertical" size={12} style={{ width: "100%" }}>
            <Alert
                type={blocks ? "warning" : "success"}
                showIcon
                title={`${blocks ? "Blokuje" : "Przepuszcza"} — zestaw reguł nr ${verdict.rules_version}`}
            />
            {verdict.reasons.length > 0 && <Bullets title="Dlaczego" items={verdict.reasons} />}
            {verdict.hint !== "" && <Bullets title="Wskazówki" items={[verdict.hint]} />}
        </Space>
    );
}

/**
 * Description:
 * Sekcja werdyktu: nagłówek i punkty — powody albo to, co dopisać.
 *
 * Example args:
 *     title="Dlaczego"
 *     items=["Nie widać, co zrobiono."]
 *
 * Example result:
 *     <List> z nagłówkiem „Dlaczego" i jednym punktem
 */
function Bullets({ title, items }: { title: string; items: string[] }) {
    return (
        <List
            size="small"
            header={<strong>{title}</strong>}
            dataSource={items}
            renderItem={(item) => <List.Item>{item}</List.Item>}
        />
    );
}

/**
 * Description:
 * Karta zgłoszenia pole po polu, z nazwą pola z kontraktu pod nazwą dla człowieka — tak, jak
 * zgłoszenie wyglądałoby w bazie wiedzy.
 *
 * Example args:
 *     card={ component: "e-Doręczenia", problem: "…", error_codes: ["…"], … }
 *
 * Example result:
 *     <Descriptions> z ośmioma wierszami
 */
function CardView({ card }: { card: TicketCard }) {
    const items = CARD_FIELDS.map(({ label, field }) => {
        const value = card[field];

        return {
            key:      field,
            label:    <Space orientation="vertical" size={0}>{label}<span className="mono muted">{field}</span></Space>,
            children: Array.isArray(value)
                ? <Space wrap size={4}>{value.map((code) => <Tag key={code} className="mono">{code}</Tag>)}</Space>
                : <span style={{ whiteSpace: "pre-wrap" }}>{String(value)}</span>,
        };
    });

    return <Descriptions column={1} bordered size="small" items={items} />;
}
