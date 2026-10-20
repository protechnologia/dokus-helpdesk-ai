/**
 * Description:
 * Prawa kolumna: ciemna konsola przebiegów od otwarcia strony. Każdy przebieg to karta z tytułem
 * i licznikami, którą można zwinąć, a w niej wiersze kroków — anonimizacja, tury modelu, pod nimi
 * wywołania narzędzi, odpowiedź i krok w toku, każdy rodzaj w swoim kolorze. Kliknięty wiersz
 * otwiera dialog z zapytaniem i odpowiedzią albo z tokenami tury. Guzik „pokaż" przy
 * zakończonym przebiegu wczytuje jego wynik do środkowego panelu, a „Wyczyść" w nagłówku
 * zdejmuje z konsoli zakończone przebiegi.
 *
 * Kto czyta: `pages/App.tsx` podaje przebiegi z `useRuns()` i numer pokazanego przebiegu,
 * a dostaje numer przebiegu do pokazania; wiersze składa `runs/rows.ts`, a dialog rysuje
 * `StepDialog.tsx`.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Przebiegi stoją w kolejności uruchomienia; nowy przebieg rozwija się, a poprzednie się
 *   zwijają, i konsola przewija się do niego — dalej człowiek rozwija i zwija je sam.
 * - Wiersz w toku nie ma dialogu: jego krok jeszcze nie przyszedł. Wiersz, którego dialog jest
 *   otwarty, jest podświetlony.
 * - „Wyczyść" tylko chowa przebiegi w konsoli: zostają w pamięci strony, więc liczniki belki
 *   dalej liczą się od otwarcia strony, a wczytany do środkowego panelu przebieg tam zostaje.
 *   Przebiegu w toku nie chowa.
 * - Wygląd idzie za szkicem układu z p. 77; kolory rodzajów kroków stoją w `styles/app.css`
 *   (`console-row[data-kind]`).
 */

import { ClearOutlined, DownOutlined, EyeOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import { useEffect, useRef, useState } from "react";

import type { ConsoleRow } from "../../models/runs/console";
import type { Run } from "../../models/runs/run";
import { runRows, runSummary } from "../../runs/rows";
import { StepDialog } from "./StepDialog";

/** Właściwości konsoli przebiegu. */
interface ConsolePanelProps {
    runs:    Run[];                 // przebiegi z useRuns(), w kolejności uruchomienia
    now:     number;                // Date.now() — czas kroku w toku
    shownId: number | null;         // numer przebiegu w środkowym panelu
    onShow:  (id: number) => void;  // np. setShownId — wczytanie przebiegu do środkowego panelu
}

/**
 * Description:
 * Konsola: karty przebiegów z wierszami kroków, guzik czyszczenia i dialog szczegółów
 * klikniętego wiersza.
 *
 * Example args:
 *     runs=[Run(title="Rozpoznanie", …), Run(title="Rozwiązanie", …)]
 *     now=Date.now()
 *     shownId=2
 *     onShow=setShownId
 *
 * Example result:
 *     <section className="column console"> z dwiema kartami, rozwiniętą ostatnią
 */
export function ConsolePanel({ runs, now, shownId, onShow }: ConsolePanelProps) {
    // Numery rozwiniętych przebiegów.
    const [open, setOpen]     = useState<number[]>([]);
    // Kliknięty wiersz, którego dialog jest otwarty; null — dialog zamknięty.
    const [picked, setPicked] = useState<ConsoleRow | null>(null);
    // Numer ostatniego przebiegu schowanego „Wyczyść"; przebiegi do niego włącznie nie stoją
    // w konsoli, chyba że jeszcze trwają.
    const [hiddenUpTo, setHiddenUpTo] = useState(0);
    // Znacznik końca konsoli, do którego przewija się przy nowym przebiegu.
    const bottom              = useRef<HTMLDivElement>(null);
    const lastId              = runs.at(-1)?.id;
    const running             = runs.some((run) => run.finishedAt === null);
    const visible             = runs.filter((run) => run.id > hiddenUpTo || run.finishedAt === null);
    const finished            = visible.filter((run) => run.finishedAt !== null);

    // --- nowy przebieg: rozwinąć tylko jego i pokazać go w konsoli ---
    useEffect(() => {
        if (lastId === undefined) {
            return;
        }

        setOpen([lastId]);
        bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [lastId]);

    /**
     * Description:
     * Zwija rozwinięty przebieg albo rozwija zwinięty.
     *
     * Example args:
     *     id=3
     *
     * Example result:
     *     undefined — przebieg 3 zmienia stan rozwinięcia
     */
    const toggle = (
        id: number,  // numer przebiegu
    ) => setOpen((ids) => (ids.includes(id) ? ids.filter((other) => other !== id) : [...ids, id]));

    /**
     * Description:
     * Chowa z konsoli zakończone przebiegi; przebieg w toku zostaje.
     *
     * Example args:
     *     (brak)
     *
     * Example result:
     *     undefined — konsola pokazuje tylko przebieg w toku albo nic
     */
    const clear = () => setHiddenUpTo(finished.at(-1)?.id ?? hiddenUpTo);

    return (
        <section className="column column-console console" aria-label="Konsola przebiegu">
            <div className="column-header">
                <h2>Konsola przebiegu</h2>
                <span className="console-tools">
                    {running && <span className="console-live"><span className="live-dot" aria-hidden="true" />na żywo</span>}
                    <Button
                        size="small"
                        type="text"
                        className="console-button"
                        icon={<ClearOutlined />}
                        disabled={finished.length === 0}
                        onClick={clear}
                    >
                        Wyczyść
                    </Button>
                </span>
            </div>
            {visible.length === 0 && (
                <p className="console-empty">
                    {runs.length === 0 ? "Tu pojawią się kroki przebiegów." : "Konsola wyczyszczona — liczniki na górze liczą dalej od otwarcia strony."}
                </p>
            )}
            {visible.map((run) => (
                <RunBlock
                    key={run.id}
                    run={run}
                    now={now}
                    open={open.includes(run.id)}
                    shown={run.id === shownId}
                    pickedKey={picked?.key ?? null}
                    onToggle={() => toggle(run.id)}
                    onShow={() => onShow(run.id)}
                    onPick={setPicked}
                />
            ))}
            <div ref={bottom} />
            <StepDialog detail={picked?.detail ?? null} onClose={() => setPicked(null)} />
        </section>
    );
}

/** Właściwości karty jednego przebiegu. */
interface RunBlockProps {
    run:       Run;                         // przebieg z useRuns()
    now:       number;                      // Date.now() — czas kroku w toku
    open:      boolean;                     // czy wiersze są rozwinięte
    shown:     boolean;                     // czy przebieg stoi w środkowym panelu
    pickedKey: string | null;               // klucz wiersza z otwartym dialogiem
    onToggle:  () => void;                  // zwinięcie albo rozwinięcie karty
    onShow:    () => void;                  // wczytanie przebiegu do środkowego panelu
    onPick:    (row: ConsoleRow) => void;   // kliknięcie wiersza z dialogiem
}

/**
 * Description:
 * Karta przebiegu: nagłówek (strzałka, tytuł i liczniki zwijają kartę; obok guzik „pokaż" albo
 * znacznik „w panelu") i, gdy rozwinięta, siatka wierszy start | krok | koszt | czas.
 *
 * Example args:
 *     run=Run(title="Rozwiązanie", ticketId="90101", …)
 *     now=Date.now()
 *     open=true
 *     shown=false
 *     pickedKey=null
 *     onToggle=() => …
 *     onShow=() => onShow(3)
 *     onPick=setPicked
 *
 * Example result:
 *     <div className="run-block"> z „Rozwiązanie · 90101   6 tur · 7 narzędzi · …", guzikiem
 *     „pokaż" i wierszami
 */
function RunBlock({ run, now, open, shown, pickedKey, onToggle, onShow, onPick }: RunBlockProps) {
    const running = run.finishedAt === null;

    return (
        <div className="run-block" data-running={running} data-shown={shown}>
            <div className="run-block-header">
                <button type="button" className="run-block-toggle" aria-expanded={open} onClick={onToggle}>
                    {open ? <DownOutlined /> : <RightOutlined />}
                    <span className="run-block-title">{run.title} · {run.ticketId || "bez numeru"}</span>
                    <span className="run-block-summary">{runSummary(run, now)}</span>
                </button>
                {shown ? (
                    // --- ten przebieg już stoi w środkowym panelu ---
                    <span className="run-block-shown">w panelu</span>
                ) : (
                    <Tooltip title="Pokaż wynik tego przebiegu w środkowym panelu">
                        <Button
                            size="small"
                            type="text"
                            className="console-button"
                            icon={<EyeOutlined />}
                            disabled={running}
                            onClick={onShow}
                        >
                            pokaż
                        </Button>
                    </Tooltip>
                )}
            </div>
            {open && (
                <>
                    <div className="console-grid console-head">
                        <span>start</span><span>krok</span><span className="right">koszt</span><span className="right">czas</span>
                    </div>
                    {runRows(run, now).map((row) => (
                        <button
                            key={row.key}
                            type="button"
                            className="console-row console-grid"
                            data-kind={row.kind}
                            aria-pressed={row.key === pickedKey}
                            disabled={row.detail === null}
                            onClick={() => onPick(row)}
                        >
                            <span className="start">{row.start}</span>
                            <span className="step">
                                <span className="label">
                                    {row.kind === "pending" && <span className="live-dot" aria-hidden="true" />}
                                    {row.label}
                                </span>
                                {row.summary !== "" && <span className="summary">{row.summary}</span>}
                            </span>
                            <span className="right cost">{row.cost}</span>
                            <span className="right">{row.duration}</span>
                        </button>
                    ))}
                    {run.error !== null && <p className="run-block-error">błąd: {run.error}</p>}
                </>
            )}
        </div>
    );
}
