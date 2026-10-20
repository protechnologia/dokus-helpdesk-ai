/**
 * Description:
 * Wygląd frontu przez tokeny antd: kolor wiodący, czcionki i zaokrąglenia, oraz wygląd pustych
 * miejsc (`EMPTY`) dla wszystkich komponentów `Empty` naraz. Czyta go
 * `ConfigProvider` w `main.tsx`; układ strony (kolumny, konsola) stoi obok, w `app.css`.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Wygląd zmienia się tutaj, nie w stylach komponentów: tokeny przenoszą się na wszystkie
 *   komponenty antd naraz (CLAUDE.md → „Frontend": bez Tailwinda, tokeny w `ConfigProvider`).
 * - Czcionki IBM Plex ładuje `index.html`; bez sieci strona spada na czcionkę systemową.
 */

import { Empty } from "antd";
import type { ConfigProviderProps, ThemeConfig } from "antd";

// Czcionka tekstu i czcionka o stałej szerokości (zapytania, wyniki narzędzi, kody błędów).
export const FONT_SANS = "'IBM Plex Sans', system-ui, sans-serif";
export const FONT_MONO = "'IBM Plex Mono', ui-monospace, monospace";

export const THEME: ThemeConfig = {
    token: {
        colorPrimary:   "#1668dc",
        colorBgLayout:  "#f2f3f5",
        fontFamily:     FONT_SANS,
        fontFamilyCode: FONT_MONO,
        fontSize:       14,
        borderRadius:   6,
    },
};

// Puste miejsca (wątek bez komentarzy, brak źródeł, brak uwag): mała ikona i mały odstęp. Domyślne
// 32 px nad i pod ikoną wysoką na 40 px zostawiały w kolumnach za dużo wolnego miejsca.
export const EMPTY: ConfigProviderProps["empty"] = {
    image:  Empty.PRESENTED_IMAGE_SIMPLE,
    styles: {
        root:  { marginBlock: 8 },
        image: { height: 28, marginBottom: 4 },
    },
};

// Pola tekstowe (treść zgłoszenia, komentarz, szkic dla klienta) z uchwytem do zmiany wysokości.
// Bez samorozciągania antd (`autoSize`), które uchwyt wyłącza: długi tekst przewija się w polu,
// a wysokość ustawia człowiek.
export const RESIZABLE = { resize: "vertical" as const };
