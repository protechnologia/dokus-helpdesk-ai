/**
 * Description:
 * Układ trzech kolumn pod pasem guzików — zgłoszenie, odpowiedź i konsola — z suwakami między
 * nimi: szerokość kolumn reguluje się przeciągnięciem, a podwójne kliknięcie suwaka przywraca
 * szerokości domyślne. Na wąskim ekranie suwaków nie ma, a kolumny stają jedna pod drugą.
 *
 * Kto czyta: `pages/App.tsx` podaje trzy kolumny (panele z `pages/panels/`) jako dzieci.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Szerokości pamięta przeglądarka (`localStorage`, w procentach), więc wracają po odświeżeniu.
 *   To wygoda jednej osoby, nie stan strony: odczyt i zapis są w try/catch, a zła albo
 *   niedostępna pamięć daje szerokości domyślne.
 * - Granica „szeroki ekran" to `xl` z antd (1200 px), ta sama co w `styles/app.css`
 *   (`@media (max-width: 1199.98px)`): poniżej kolumny układa CSS, bez suwaków.
 * - Podwójne kliknięcie przebudowuje suwaki od nowa (klucz `layout`), bo `Splitter` bez sterowania
 *   z zewnątrz bierze `defaultSize` tylko przy pierwszym rysowaniu.
 */

import { Grid, Splitter } from "antd";
import type { ReactNode } from "react";
import { useState } from "react";

// Klucz szerokości kolumn w pamięci przeglądarki.
const STORAGE_KEY = "helpdesk-ai.columns";

// Szerokości domyślne w procentach: odpowiedź najszersza, konsola szersza od zgłoszenia.
const DEFAULT_SIZES = [22, 47, 31];

// Najmniejsza szerokość kolumny w pikselach, żeby żadnej nie dało się zgnieść do zera.
const MIN_WIDTHS = [240, 360, 300];

/** Właściwości układu kolumn. */
interface ColumnsProps {
    children: [ReactNode, ReactNode, ReactNode];  // zgłoszenie, odpowiedź, konsola — w tej kolejności
}

/**
 * Description:
 * Trzy kolumny z suwakami na szerokim ekranie albo jedna pod drugą na wąskim.
 *
 * Example args:
 *     children=[<TicketPanel …/>, <AnswerPanel …/>, <ConsolePanel …/>]
 *
 * Example result:
 *     <Splitter className="columns columns-split"> z trzema panelami i dwoma suwakami
 */
export function Columns({ children }: ColumnsProps) {
    // Czy ekran jest szeroki (`xl`); przed pierwszym pomiarem antd oddaje undefined — wtedy szeroki.
    const wide                = Grid.useBreakpoint().xl ?? true;
    // Numer układu suwaków; zmiana przebudowuje je z szerokościami domyślnymi.
    const [layout, setLayout] = useState(0);
    // Szerokości przy pierwszym rysowaniu tego układu: zapamiętane albo domyślne.
    const sizes               = layout === 0 ? readSizes() : DEFAULT_SIZES;

    // --- wąski ekran: kolumny jedna pod drugą, bez suwaków ---
    if (!wide) {
        return <div className="columns">{children}</div>;
    }

    /**
     * Description:
     * Przywraca szerokości domyślne i zapomina zapamiętane.
     *
     * Example args:
     *     (brak)
     *
     * Example result:
     *     undefined — kolumny w proporcjach 22 / 47 / 31
     */
    const reset = () => {
        writeSizes(null);
        setLayout((current) => current + 1);
    };

    return (
        <Splitter
            key={layout}
            className="columns columns-split"
            onResizeEnd={(pixels) => writeSizes(asPercents(pixels))}
            onDraggerDoubleClick={reset}
        >
            {children.map((column, index) => (
                <Splitter.Panel key={index} defaultSize={`${sizes[index]}%`} min={MIN_WIDTHS[index]}>
                    {column}
                </Splitter.Panel>
            ))}
        </Splitter>
    );
}

/**
 * Description:
 * Zamienia szerokości w pikselach na procenty całości, żeby pasowały do okna innej szerokości.
 *
 * Example args:
 *     pixels=[300, 700, 400]
 *
 * Example result:
 *     [21.43, 50, 28.57]
 */
function asPercents(
    pixels: number[],  // np. szerokości paneli z `onResizeEnd`
): number[] {
    const total = pixels.reduce((sum, width) => sum + width, 0);

    return pixels.map((width) => Math.round((width / total) * 10000) / 100);
}

/**
 * Description:
 * Zapamiętane szerokości kolumn albo domyślne, gdy pamięci nie ma, jest niedostępna albo niesie
 * coś innego niż trzy dodatnie liczby.
 *
 * Example args:
 *     (brak)
 *
 * Example result:
 *     [22, 47, 31]
 */
function readSizes(): number[] {
    try {
        const saved: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null");
        const valid = Array.isArray(saved)
            && saved.length === DEFAULT_SIZES.length
            && saved.every((size) => typeof size === "number" && size > 0);

        return valid ? (saved as number[]) : DEFAULT_SIZES;
    } catch {
        // Pamięć przeglądarki bywa wyłączona albo zablokowana; wtedy zostają szerokości domyślne.
        return DEFAULT_SIZES;
    }
}

/**
 * Description:
 * Zapisuje szerokości kolumn w pamięci przeglądarki; `null` je kasuje. Błąd zapisu nie przeszkadza
 * stronie: po odświeżeniu wrócą szerokości domyślne.
 *
 * Example args:
 *     sizes=[21.43, 50, 28.57]
 *
 * Example result:
 *     undefined — szerokości w `localStorage` pod `helpdesk-ai.columns`
 */
function writeSizes(
    sizes: number[] | null,  // np. procenty z asPercents(); null — zapomnieć
): void {
    try {
        if (sizes === null) {
            window.localStorage.removeItem(STORAGE_KEY);

            return;
        }

        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sizes));
    } catch {
        // Pamięć przeglądarki bywa wyłączona albo pełna; szerokości po prostu nie wrócą po odświeżeniu.
    }
}
