/**
 * Description:
 * Pas guzików grafów nad kolumnami: rozpoznanie i warianty odpowiedzi z `GET /variants` (pełne,
 * niebieskie), a za kreską karta zgłoszenia i bramka zamknięcia (ciemne) — wszystko, co działa na
 * zgłoszeniu z lewego panelu. Guziki na szkicu dla klienta („Sprawdź przed wysyłką", „Popraw")
 * stoją w `ClientTab.tsx`.
 *
 * Kto czyta: `pages/App.tsx` umieszcza pas pod belką i dostaje od niego kliknięty guzik
 * (`GraphAction`), po czym uruchamia graf.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Guziki to dane (`BEFORE_VARIANTS`, `AFTER_VARIANTS`, `ICONS`), nie JSX: nowy guzik to wpis
 *   na liście. Warianty przychodzą z `api`, więc nowy wariant w `api` pojawia się tu sam.
 * - Dwie grupy różnią się kolorem celowo: pierwsza odpowiada na zgłoszenie, druga je ocenia.
 * - Wariant bez ikony w `ICONS` dostaje ikonę ogólną, a nie znika.
 * - Warianty stoją w kolejności pracy nad sprawą (`VARIANT_ORDER`): najpierw pytania, potem
 *   odpowiedź, na końcu przekazanie. `api` oddaje je alfabetycznie, a kolejność to sprawa
 *   wyglądu, nie kontraktu; wariant spoza listy staje na końcu, w kolejności z `api`.
 */

import {
    BulbOutlined,
    IdcardOutlined,
    MessageOutlined,
    QuestionCircleOutlined,
    SafetyCertificateOutlined,
    SearchOutlined,
    SendOutlined,
} from "@ant-design/icons";
import { Button } from "antd";
import type { ReactNode } from "react";

import type { VariantInfo } from "../../models/api/suggest";
import type { TicketRequest } from "../../models/api/ticket";
import type { GraphAction } from "../../models/runs/graph";

// Guziki przed wariantami odpowiedzi: najpierw rozpoznanie sprawy.
const BEFORE_VARIANTS: GraphAction[] = [
    { kind: "search", title: "Rozpoznanie" },
];

// Guziki po wariantach, za kreską: to, co ocenia zgłoszenie, a nie odpowiada na nie.
const AFTER_VARIANTS: GraphAction[] = [
    { kind: "parse_ticket", title: "Karta zgłoszenia" },
    { kind: "gate_close",   title: "Bramka zamknięcia" },
];

// Kolejność wariantów w pasie: tak, jak idzie praca nad sprawą.
const VARIANT_ORDER = ["questions", "solution", "handoff"];

// Ikona guzika po wariancie albo po grafie; czego tu nie ma, dostaje `MessageOutlined`.
const ICONS: Record<string, ReactNode> = {
    search:       <SearchOutlined />,
    questions:    <QuestionCircleOutlined />,
    solution:     <BulbOutlined />,
    handoff:      <SendOutlined />,
    parse_ticket: <IdcardOutlined />,
    gate_close:   <SafetyCertificateOutlined />,
};

/** Właściwości pasa guzików. */
interface GraphButtonsProps {
    variants: VariantInfo[];                  // z GET /variants; pusta lista, dopóki nie przyjdzie
    ticket:   TicketRequest;                  // zgłoszenie z lewego panelu — do podpisu przed guzikami
    disabled: boolean;                        // true, gdy trwa przebieg
    onRun:    (action: GraphAction) => void;  // np. (action) => runOnTicket(action)
}

/**
 * Description:
 * Pas guzików z podpisem, na którym zgłoszeniu zadziałają.
 *
 * Example args:
 *     variants=[{ name: "questions", label: "Jakie pytania zadać", requires_hits: false }, …]
 *     ticket={ ticket_id: "90101", subject: "Brak nowych przesyłek…", … }
 *     disabled=false
 *     onRun=(action) => …
 *
 * Example result:
 *     <section className="run-band"> z „Uruchom na zgłoszeniu 90101 · …" i sześcioma guzikami
 */
export function GraphButtons({ variants, ticket, disabled, onRun }: GraphButtonsProps) {
    const fromVariants: GraphAction[] = inWorkOrder(variants).map((variant) => ({
        kind:    "suggest",
        title:   variant.label,
        variant: variant.name,
    }));

    const label = [ticket.ticket_id || "bez numeru", ticket.subject].filter(Boolean).join(" · ");

    /**
     * Description:
     * Jeden guzik grafu: pełny niebieski albo ciemny, z ikoną po wariancie albo po grafie.
     *
     * Example args:
     *     action={ kind: "gate_close", title: "Bramka zamknięcia" }
     *     dark=true
     *
     * Example result:
     *     <Button color="default" variant="solid"> z tarczą i „Bramka zamknięcia"
     */
    const button = (
        action: GraphAction,  // np. { kind: "search", title: "Rozpoznanie" }
        dark:   boolean,      // true dla guzików, które oceniają zgłoszenie
    ) => (
        <Button
            key={`${action.kind}-${action.variant ?? ""}`}
            color={dark ? "default" : "primary"}
            variant="solid"
            icon={ICONS[action.variant ?? action.kind] ?? <MessageOutlined />}
            disabled={disabled}
            onClick={() => onRun(action)}
        >
            {action.title}
        </Button>
    );

    return (
        <section className="run-band" aria-label="Uruchom na zgłoszeniu">
            <p className="run-band-label">
                <span>Uruchom na zgłoszeniu</span> <strong>{label}</strong>
            </p>
            <div className="run-band-buttons">
                {[...BEFORE_VARIANTS, ...fromVariants].map((action) => button(action, false))}
                <span className="run-band-separator" aria-hidden="true" />
                {AFTER_VARIANTS.map((action) => button(action, true))}
            </div>
        </section>
    );
}

/**
 * Description:
 * Warianty w kolejności pracy nad sprawą (`VARIANT_ORDER`); nieznane na końcu, w kolejności
 * z `api`.
 *
 * Example args:
 *     variants=[{ name: "handoff", … }, { name: "questions", … }, { name: "solution", … }]
 *
 * Example result:
 *     [{ name: "questions", … }, { name: "solution", … }, { name: "handoff", … }]
 */
function inWorkOrder(
    variants: VariantInfo[],  // np. odpowiedź GET /variants
): VariantInfo[] {
    // Miejsce na liście; wariant spoza listy dostaje miejsce za wszystkimi znanymi.
    const rank = (variant: VariantInfo) => {
        const index = VARIANT_ORDER.indexOf(variant.name);

        return index === -1 ? VARIANT_ORDER.length : index;
    };

    // `sort` jest stabilny, więc nieznane warianty zostają w kolejności z `api`.
    const ordered = [...variants].sort((left, right) => rank(left) - rank(right));

    return ordered;
}
