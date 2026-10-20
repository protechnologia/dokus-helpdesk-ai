/**
 * Description:
 * Punkt wejścia frontu: montuje aplikację w `#root` z `index.html`, z motywem antd
 * (`styles/theme.ts`) i stylami układu strony (`styles/app.css`).
 *
 * O czym pamiętać przy zmianach:
 *
 * - `App` z antd (tu `AntApp`) daje komponentom kontekst komunikatów i dialogów z motywem;
 *   nasza strona to `App` z `pages/App.tsx`.
 * - `StrictMode` w dev woła efekty dwa razy; odczyty `GET /instance` i `GET /variants` to
 *   wytrzymują, bo są tylko do odczytu.
 */

import { App as AntApp, ConfigProvider } from "antd";
import plPL from "antd/locale/pl_PL";
import dayjs from "dayjs";
import "dayjs/locale/pl";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/app.css";
import { App } from "./pages/App";
import { EMPTY, THEME } from "./styles/theme";

// Nazwy miesięcy i dni w kalendarzu po polsku: antd bierze je z dayjs, a nie z `locale` ConfigProvidera.
dayjs.locale("pl");

const root = document.getElementById("root");

// --- bez kontenera z index.html nie ma czego montować: błąd od razu, nie biała strona ---
if (root === null) {
    throw new Error("brak elementu #root w index.html");
}

createRoot(root).render(
    <StrictMode>
        <ConfigProvider theme={THEME} locale={plPL} empty={EMPTY}>
            <AntApp>
                <App />
            </AntApp>
        </ConfigProvider>
    </StrictMode>,
);
