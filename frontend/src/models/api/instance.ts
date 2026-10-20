/**
 * Description:
 * Stan instancji z `GET /instance`: model generujący, anonimizator, stan indeksów narzędzi i gałąź
 * paczki kodu — przepisany z `api/app/entry_routers/instance/models.py`.
 *
 * Kto czyta: `pages/panels/TopBar.tsx` — belka u góry pokazuje oba modele i stan każdego materiału,
 * więc widać, kto anonimizuje i generuje, i czy „nic nie znaleziono" znaczy, że materiał milczy, czy
 * że indeks jest pusty.
 */

/** Model generujący: dostawca i nazwa; przy atrapie (`fake`) bez nazwy. */
export interface GenerationModelInfo {
    provider: string;         // np. "openai"
    name:     string | null;  // np. "gpt-6.1-sol"
}

/** Anonimizator: czy usługa `anonymizer` odpowiada, którym silnikiem i z jakim modelem działa. */
export interface AnonymizationInfo {
    state:  "available" | "unavailable";
    engine: string | null;  // np. "agent"; null, gdy usługa nie odpowiada
    model:  string | null;  // np. "speakleash/Bielik-11B-v3.0"; null przy atrapie silnika
}

/** Stan jednego indeksu, na którym stoją narzędzia agenta. */
export interface IndexItem {
    material: "tickets" | "docs" | "code";
    index:    "cards" | "threads" | "sections" | "fragments" | "package";
    state:    "missing" | "empty" | "built";
    count:    number | null;  // np. 171; null, gdy indeksu nie ma
}

/** Gałąź i dzień budowy paczki kodu aplikacji. */
export interface CodePackageItem {
    branch:   string | null;  // np. "/main/stage-gminy"
    built_on: string;         // np. "2026-10-07"
}

/** Odpowiedź `GET /instance`. */
export interface InstanceResponse {
    model:         GenerationModelInfo;
    anonymization: AnonymizationInfo;
    indexes:       IndexItem[];
    code_package:  CodePackageItem | null;
}
