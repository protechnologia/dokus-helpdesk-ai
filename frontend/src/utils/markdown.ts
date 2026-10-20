/**
 * Description:
 * Przygotowanie tekstu Markdown do czytania przez człowieka.
 *
 * | funkcja               | przykład                                        |
 * |-----------------------|-------------------------------------------------|
 * | `linesAsParagraphs()` | "Ad. 1. a\nAd. 2. b" → "Ad. 1. a\n\nAd. 2. b"     |
 *
 * Kto czyta: `pages/panels/NotesTab.tsx` przed wysłaniem uwag dla wdrożeniowca do Markdownu.
 */

// Linia, która w Markdownie coś znaczy sama: punkt listy, lista numerowana, nagłówek, cytat albo
// granica bloku kodu. Takiej linii nie odsuwa się od sąsiadów, bo zmieniłoby to strukturę.
const STRUCTURAL_LINE = /^\s*([-*+]\s|\d+[.)]\s|#{1,6}\s|>|```)/;

// Granica bloku kodu: w środku bloku linie zostają znak w znak.
const FENCE = /^\s*```/;

/**
 * Description:
 * Robi z każdej zwykłej linii osobny akapit: między dwiema zwykłymi liniami wstawia pustą.
 * Markdown skleja kolejne linie w jeden akapit, a uwagi propozycji to osobne notatki w kolejnych
 * liniach („Ad. 1. …", „Ad. 2. …"); jako akapity dostają odstęp. Listy, nagłówki, cytaty i bloki
 * kodu zostają bez zmian.
 *
 * Example args:
 *     text="Ad. 1. odcina kolejkę\nAd. 2. odcina załącznik\n## Kod\n- linia 12"
 *
 * Example result:
 *     "Ad. 1. odcina kolejkę\n\nAd. 2. odcina załącznik\n## Kod\n- linia 12"
 */
export function linesAsParagraphs(
    text: string,  // np. uwagi dla wdrożeniowca
): string {
    const out: string[] = [];
    let inFence         = false;
    let previousPlain   = false;

    for (const line of text.split("\n")) {
        const fence = FENCE.test(line);
        const plain = !inFence && !fence && line.trim() !== "" && !STRUCTURAL_LINE.test(line);

        // --- dwie zwykłe linie z rzędu: pusta linia między nimi robi z nich dwa akapity ---
        if (plain && previousPlain) {
            out.push("");
        }

        out.push(line);
        previousPlain = plain;

        if (fence) {
            inFence = !inFence;
        }
    }

    return out.join("\n");
}
