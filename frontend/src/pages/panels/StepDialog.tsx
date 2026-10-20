/**
 * Description:
 * Dialog szczegółów kroku nad stroną: po kliknięciu wiersza konsoli pokazuje zapytanie
 * i odpowiedź wywołania narzędzia, tokeny i wywołania tury modelu albo wpis logu. Treść, która
 * jest obiektem JSON (zapytanie, odpowiedź narzędzia), idzie przez przeglądarkę JSON-a
 * z `react-json-view-lite`: klucze da się zwijać i rozwijać, a na start rozwinięte są dwa
 * poziomy. Inną treść pokazuje zwykły blok, a długą skraca, z guzikiem „Pokaż całość".
 *
 * Kto czyta: `ConsolePanel.tsx` otwiera dialog z treścią, którą dla wiersza złożył
 * `runs/rows.ts`.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Odpowiedź narzędzia to tekst, który dostał model, czasem kilkadziesiąt tysięcy znaków
 *   (odczyt pliku kodu); bez skrócenia dialog przewijałby się bez końca.
 * - Każda część dialogu pamięta „Pokaż całość" i zwinięte klucze osobno; zamknięcie dialogu
 *   zapomina wszystko.
 * - JSON nie jest skracany: długą odpowiedź (karty, odczyt pliku kodu) zwija się kluczami.
 * - Przeglądarka JSON-a zwija klucze od nowa, gdy dostanie nową funkcję `shouldExpandNode`, a w
 *   trakcie przebiegu strona przerysowuje się co 200 ms (zegar). Dlatego funkcja stoi w module
 *   (`expandFirstLevels`), a rozbiór JSON-a jest zapamiętany (`useMemo`): rozwinięte klucze nie
 *   zamykają się same.
 * - Dialog mieści się w oknie: ma najwyżej wysokość okna, a treść przewija się w środku.
 * - Dialog przesuwa się za nagłówek, a rozmiar zmienia za prawy dolny róg (CSS `resize`), bez
 *   osobnej biblioteki. Przeciąganie startuje tylko z nagłówka, bo w treści człowiek zaznacza
 *   tekst i zwija klucze; zamknięcie wraca dialog na środek, a rozmiar zostaje.
 */

import { Button, Modal, Space, Typography } from "antd";
import { useMemo, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { JsonView } from "react-json-view-lite";

import type { DetailSection, StepDetail } from "../../models/runs/console";
import { parseJsonObject } from "../../utils/json";

// Ile znaków treści widać przed „Pokaż całość"; mieści się w tym typowy wynik wyszukiwania.
const PREVIEW_CHARS = 4000;

// Ile poziomów JSON-a jest rozwiniętych na start: przy kartach zgłoszeń to lista i pola kart.
const EXPANDED_LEVELS = 2;

/**
 * Description:
 * Mówi przeglądarce JSON-a, które poziomy rozwinąć na start: pierwsze `EXPANDED_LEVELS`. Funkcja
 * stoi w module, żeby była ta sama przy każdym rysowaniu; nowa funkcja zwijałaby klucze
 * rozwinięte przez człowieka.
 *
 * Example args:
 *     level=1
 *
 * Example result:
 *     true
 */
function expandFirstLevels(
    level: number,  // np. 0 — korzeń JSON-a
): boolean {
    return level < EXPANDED_LEVELS;
}

// Wygląd przeglądarki JSON-a: własne klasy z `styles/app.css` zamiast stylów biblioteki, które
// pogrubiały klucze i nawiasy na szarym tle; ramka i czcionka jak w bloku kodu.
const JSON_STYLES = {
    container:            "code-block json-view",
    basicChildStyle:      "json-child",
    childFieldsContainer: "json-children",
    label:                "json-key",
    clickableLabel:       "json-key json-clickable",
    nullValue:            "json-null",
    undefinedValue:       "json-null",
    stringValue:          "json-string",
    booleanValue:         "json-literal",
    numberValue:          "json-literal",
    otherValue:           "json-other",
    punctuation:          "json-punctuation",
    expandIcon:           "json-icon json-expand",
    collapseIcon:         "json-icon json-collapse",
    collapsedContent:     "json-collapsed",
    ariaLables:           { collapseJson: "zwiń", expandJson: "rozwiń" },
    stringifyStringValues: false,
};

// Okno dialogu: rozmiar zmienia się za prawy dolny róg, najwyżej do wysokości okna przeglądarki;
// kolumna, żeby treść pod nagłówkiem dostała całą resztę wysokości.
const CONTAINER_STYLE = {
    resize:        "both" as const,
    overflow:      "hidden" as const,
    display:       "flex",
    flexDirection: "column" as const,
    minWidth:      420,
    minHeight:     200,
    maxHeight:     "calc(100vh - 48px)",
};

// Treść dialogu zajmuje resztę wysokości i przewija się w środku, pod nieruchomym tytułem.
const BODY_STYLE = {
    flex:      "1 1 auto",
    minHeight: 0,
    overflowY: "auto" as const,
};

// Przesunięcie dialogu, gdy stoi na środku ekranu.
const CENTER = { x: 0, y: 0 };

/** Właściwości dialogu szczegółów. */
interface StepDialogProps {
    detail:  StepDetail | null;  // null — dialog zamknięty
    onClose: () => void;         // np. () => setDetail(null)
}

/**
 * Description:
 * Dialog szczegółów; zamknięty, gdy nie ma treści do pokazania. Przesuwa się za nagłówek.
 *
 * Example args:
 *     detail={ title: "find_tickets_vector · tura 1", meta: "start 00:03.0 · 412 ms", sections: [ … ] }
 *     onClose=() => setDetail(null)
 *
 * Example result:
 *     <Modal> z tytułem, linią „start 00:03.0 · 412 ms" i częściami „Zapytanie", „Odpowiedź"
 */
export function StepDialog({ detail, onClose }: StepDialogProps) {
    // Przesunięcie dialogu względem środka ekranu po przeciągnięciu za nagłówek.
    const [offset, setOffset] = useState(CENTER);

    /**
     * Description:
     * Zaczyna przeciąganie dialogu, gdy człowiek chwycił nagłówek (ale nie krzyżyk); dialog idzie
     * za wskaźnikiem do puszczenia przycisku.
     *
     * Example args:
     *     event=PointerEvent(target=<div className="ant-modal-header">, clientX=400, clientY=120)
     *
     * Example result:
     *     undefined — dialog przesuwa się razem z wskaźnikiem
     */
    const startDrag = (
        event: ReactPointerEvent<HTMLDivElement>,  // wciśnięcie przycisku nad dialogiem
    ) => {
        const target = event.target as HTMLElement;

        // --- przeciąga się tylko za nagłówek: w treści zaznacza się tekst i zwija klucze ---
        if (target.closest(".ant-modal-header") === null || target.closest(".ant-modal-close") !== null) {
            return;
        }

        const grab = { x: event.clientX - offset.x, y: event.clientY - offset.y };

        // Dialog idzie za wskaźnikiem, a puszczenie przycisku kończy przeciąganie.
        const move = (moved: PointerEvent) => setOffset({ x: moved.clientX - grab.x, y: moved.clientY - grab.y });
        const stop = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
        };

        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", stop);
        event.preventDefault();
    };

    /**
     * Description:
     * Zamyka dialog i wraca go na środek ekranu na następne otwarcie.
     *
     * Example args:
     *     (brak)
     *
     * Example result:
     *     undefined — dialog zamknięty, przesunięcie wyzerowane
     */
    const close = () => {
        setOffset(CENTER);
        onClose();
    };

    return (
        <Modal
            open={detail !== null}
            title={detail?.title}
            footer={null}
            width={760}
            centered
            rootClassName="step-dialog"
            styles={{ container: CONTAINER_STYLE, body: BODY_STYLE }}
            modalRender={(node) => (
                <div style={{ transform: `translate(${offset.x}px, ${offset.y}px)` }} onPointerDown={startDrag}>
                    {node}
                </div>
            )}
            onCancel={close}
            destroyOnHidden
        >
            {detail !== null && (
                <Space orientation="vertical" size={14} style={{ width: "100%" }}>
                    <span className="muted">{detail.meta}</span>
                    {detail.sections.map((section) => <SectionBlock key={section.heading} section={section} />)}
                </Space>
            )}
        </Modal>
    );
}

/**
 * Description:
 * Jedna część dialogu: nagłówek z dopiskiem i treść — obiekt JSON w przeglądarce ze zwijaniem
 * kluczy, a inny tekst w czcionce stałej szerokości, skrócony do `PREVIEW_CHARS` znaków, dopóki
 * człowiek nie kliknie „Pokaż całość".
 *
 * Example args:
 *     section={ heading: "Odpowiedź", note: "to, co dostał model · 214 zn.", body: "{…}" }
 *
 * Example result:
 *     <div> z „Odpowiedź  to, co dostał model · 214 zn." i treścią
 */
function SectionBlock({ section }: { section: DetailSection }) {
    // Czy długa treść ma być pokazana w całości, a nie tylko jej początek.
    const [whole, setWhole] = useState(false);
    // Rozbiór zapamiętany: nowy obiekt przy każdym rysowaniu przerysowywałby całe drzewo JSON-a.
    const json              = useMemo(() => parseJsonObject(section.body), [section.body]);
    const long              = json === null && section.body.length > PREVIEW_CHARS;
    const body              = long && !whole ? `${section.body.slice(0, PREVIEW_CHARS)}\n…` : section.body;

    return (
        <Space orientation="vertical" size={6} style={{ width: "100%" }}>
            <Space size={8} align="baseline">
                <Typography.Text strong>{section.heading}</Typography.Text>
                {section.note !== "" && <span className="muted">{section.note}</span>}
            </Space>
            {json !== null ? (
                // --- obiekt JSON: klucze do zwijania, dwa poziomy rozwinięte na start ---
                <JsonView
                    data={json}
                    style={JSON_STYLES}
                    shouldExpandNode={expandFirstLevels}
                    clickToExpandNode
                />
            ) : (
                <pre className="code-block">{body}</pre>
            )}
            {long && (
                <Button size="small" onClick={() => setWhole(!whole)}>
                    {whole ? "Pokaż początek" : "Pokaż całość"}
                </Button>
            )}
        </Space>
    );
}
