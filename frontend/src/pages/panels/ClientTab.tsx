/**
 * Description:
 * Zakładka „Dla klienta": szkic wiadomości do klienta, który można poprawić przed wysyłką, i trzy
 * guziki pod nim — bramka wysyłki („Sprawdź przed wysyłką"), „Popraw" i kopiowanie. Szkic to
 * tekst pokazanego przebiegu (propozycja odpowiedzi, wynik „Popraw", szkic sprawdzony bramką),
 * ale można go też pisać z ręki.
 *
 * Kto czyta: `AnswerPanel.tsx` rysuje zakładkę; szkic trzyma `pages/App.tsx` i on uruchamia bramkę
 * wysyłki i „Popraw" na treści szkicu.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Przebieg bez tekstu dla klienta daje pusty szkic, a zakładka mówi dlaczego: wariant bez
 *   treści — że powód stoi w uwagach, inny graf — że tekstu dla klienta nie daje, ale wiadomość
 *   można napisać z ręki.
 * - Pusty szkic nie idzie do bramki ani do „Popraw": `api` odrzuciłoby go walidacją (422).
 */

import { CheckCircleOutlined, CopyOutlined, EditOutlined } from "@ant-design/icons";
import { Alert, App as AntApp, Button, Input, Space } from "antd";

import type { Run } from "../../models/runs/run";
import { clientTextOf } from "../../runs/answer";
import { RESIZABLE } from "../../styles/theme";

/** Właściwości zakładki „Dla klienta". */
interface ClientTabProps {
    draft:    string;                    // szkic dla klienta
    run:      Run;                       // pokazany przebieg — do informacji o braku treści
    busy:     boolean;                   // true, gdy trwa przebieg
    onChange: (draft: string) => void;   // np. setDraft
    onCheck:  () => void;                // bramka wysyłki na szkicu
    onPolish: () => void;                // „Popraw" na szkicu
}

/**
 * Description:
 * Szkic dla klienta z guzikami pod nim.
 *
 * Example args:
 *     draft="Dzień dobry, …"
 *     run=Run(outcome={ kind: "suggest", result: { text: "Dzień dobry, …", … } })
 *     busy=false
 *     onChange=setDraft
 *     onCheck=() => runOnDraft("gate_reply")
 *     onPolish=() => runOnDraft("polish")
 *
 * Example result:
 *     pole tekstu z guzikami „Sprawdź przed wysyłką", „Popraw" i „Kopiuj"
 */
export function ClientTab({ draft, run, busy, onChange, onCheck, onPolish }: ClientTabProps) {
    const { message } = AntApp.useApp();
    const empty       = draft.trim() === "";
    const noText      = clientTextOf(run) === null;
    const variant     = run.outcome?.kind === "suggest";

    /**
     * Description:
     * Kopiuje szkic do schowka i mówi o tym w komunikacie.
     *
     * Example args:
     *     (brak) — szkic z właściwości
     *
     * Example result:
     *     undefined — szkic w schowku, komunikat „Skopiowano"
     */
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(draft);
            message.success("Skopiowano treść dla klienta");
        } catch {
            // Schowek bywa niedostępny poza HTTPS i localhost; wtedy zostaje zaznaczenie z ręki.
            message.warning("Przeglądarka nie dała dostępu do schowka — zaznacz tekst i skopiuj go");
        }
    };

    return (
        <Space orientation="vertical" size={10} style={{ width: "100%" }}>
            {noText && (
                // --- przebieg bez tekstu dla klienta: dlaczego szkic jest pusty ---
                <Alert
                    type="info"
                    showIcon
                    title={variant ? "Ten wariant nie dał treści dla klienta" : "Ten przebieg nie daje treści dla klienta"}
                    description={variant
                        ? "Powód stoi w zakładce „Dla wdrożeniowca”. Wiadomość możesz napisać poniżej."
                        : "Wiadomość możesz napisać poniżej i sprawdzić ją przed wysyłką."}
                />
            )}
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="muted">Treść dla klienta — można ją poprawić przed wysyłką</span>
                <Input.TextArea value={draft} rows={12} style={RESIZABLE} onChange={(event) => onChange(event.target.value)} />
            </label>
            <Space wrap>
                <Button icon={<CheckCircleOutlined />} disabled={empty || busy} onClick={onCheck}>
                    Sprawdź przed wysyłką
                </Button>
                <Button icon={<EditOutlined />} disabled={empty || busy} onClick={onPolish}>
                    Popraw
                </Button>
                <Button icon={<CopyOutlined />} disabled={empty} onClick={copy}>
                    Kopiuj
                </Button>
            </Space>
        </Space>
    );
}
