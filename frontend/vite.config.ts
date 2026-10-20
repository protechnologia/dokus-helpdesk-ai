/**
 * Description:
 * Konfiguracja Vite: serwer deweloperski frontu w kontenerze `frontend`, budowa plików na prod
 * i testy Vitest.
 *
 * | tryb            | co robi                                                             |
 * |-----------------|---------------------------------------------------------------------|
 * | `npm run dev`   | serwer na porcie 8000 kontenera; `/api/…` idzie do `api` bez `/api`  |
 * | `npm run build` | pliki strony w `dist/`, które na prod podaje nginx                   |
 * | `npm test`      | testy z `tests/unit/frontend/` w korzeniu repo, bez przeglądarki      |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Adres `api` przychodzi z ENV (`FRONTEND_API_URL`), jak każdy adres w projekcie (zasada 1).
 *   Serwer deweloperski bez niego nie rusza: front bez `api` wyglądałby na działający, a każdy
 *   guzik kończyłby się błędem.
 * - Przedrostek `/api` istnieje tylko po stronie frontu: trasy `api` są bez niego, więc proxy go
 *   zdejmuje — tak samo robi nginx na prod (`nginx.conf.template`).
 * - Port 8000 to port kontenera, jak w pozostałych usługach; port hosta ustawia compose.
 */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Przedrostek, pod którym front woła `api`; ten sam stoi w `src/api/client.ts` i w nginx.
const API_PREFIX = "/api";

export default defineConfig(({ command, mode }) => {
    const apiUrl = process.env.FRONTEND_API_URL;

    // --- serwer deweloperski bez adresu `api`: błąd od razu, nie przy pierwszym guziku ---
    // Vitest też woła konfigurację jako `serve`, ale w trybie `test` i `api` nie potrzebuje.
    if (command === "serve" && mode !== "test" && !apiUrl) {
        throw new Error("brak FRONTEND_API_URL — adresu usługi `api`, np. http://api:8000");
    }

    const config = {
        plugins: [react()],
        server:  {
            host:       "0.0.0.0",
            port:       8000,
            strictPort: true,
            proxy:      apiUrl ? {
                [API_PREFIX]: {
                    target:  apiUrl,
                    rewrite: (path: string) => path.slice(API_PREFIX.length),  // np. "/api/search" → "/search"
                },
            } : undefined,
        },
        build: {
            // Paczka to ~1 MB, prawie w całości antd; front działa w sieci lokalnej na pokazach,
            // więc dzielenie paczki nie ma pomiaru, który by je uzasadniał. Próg wyżej niż
            // paczka, żeby ostrzeżenie mówiło tylko o realnym wzroście.
            chunkSizeWarningLimit: 1200,
        },
        // Testy leżą w korzeniu repo, jak wszystkie testy projektu (CLAUDE.md → „Testy"); typy
        // `vitest` widzą stamtąd dzięki `paths` w tsconfig.json.
        test: {
            dir:     "../tests/unit/frontend",
            include: ["**/*.test.ts"],
        },
    };

    return config;
});
