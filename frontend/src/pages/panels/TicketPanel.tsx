/**
 * Description:
 * Lewy panel: zgłoszenie, na którym działają guziki grafów — numer, data, temat, treść i wątek
 * komentarzy z rolą, z dodawaniem i usuwaniem. Bez wątku karta zgłoszenia i bramka zamknięcia
 * nie mają z czego pracować: przyczynę i to, co zrobiono, biorą z komentarzy.
 *
 * Kto czyta: `pages/App.tsx` trzyma zgłoszenie i dostaje każdą zmianę przez `onChange`; panel
 * nie ma własnej kopii zgłoszenia, tylko szkic nowego komentarza.
 *
 * O czym pamiętać przy zmianach:
 *
 * - Zgłoszenie ma kształt żądania `api` (`TicketRequest`), więc idzie do grafów bez przeróbki.
 * - Datę zgłoszenia wybiera się z kalendarza; pusta znaczy dla `api` „dziś”. Datę komentarza
 *   dodanego ręcznie wpisuje panel (czas lokalny); w zmyślonych przykładach daty
 *   są wpisane w `data/examples.ts`.
 */

import { DeleteOutlined, DownOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, DatePicker, Dropdown, Empty, Input, List, Select, Space, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { useState } from "react";

import { EMPTY_TICKET, EXAMPLES } from "../../data/examples";
import type { TicketComment, TicketRequest } from "../../models/api/ticket";
import { RESIZABLE } from "../../styles/theme";
import { formatTimestamp } from "../../utils/time";

// Kształt daty zgłoszenia w `api` (`TicketRequest.date`) i w kalendarzu.
const DATE_FORMAT = "YYYY-MM-DD";

// Role komentarza do wyboru; te same słowa stoją w etykietach wątku, który czyta model.
const ROLES = ["konsultant", "klient"];

/** Właściwości lewego panelu. */
interface TicketPanelProps {
    ticket:   TicketRequest;                       // zgłoszenie trzymane przez App.tsx
    onChange: (ticket: TicketRequest) => void;     // np. setTicket
}

/**
 * Description:
 * Panel zgłoszenia: pola, wątek i formularz nowego komentarza.
 *
 * Example args:
 *     ticket={ ticket_id: "90101", subject: "Brak nowych przesyłek…", comments: [ … ], … }
 *     onChange=setTicket
 *
 * Example result:
 *     <section className="column"> z polami zgłoszenia i listą komentarzy
 */
export function TicketPanel({ ticket, onChange }: TicketPanelProps) {
    // Rola nowego komentarza, wybrana nad polem jego treści.
    const [role, setRole] = useState(ROLES[0]);
    // Treść nowego komentarza, zanim trafi do wątku.
    const [body, setBody] = useState("");

    /**
     * Description:
     * Zmienia jedno pole zgłoszenia i oddaje całe zgłoszenie do `pages/App.tsx`.
     *
     * Example args:
     *     changes={ subject: "Nowy temat" }
     *
     * Example result:
     *     undefined — onChange({ …ticket, subject: "Nowy temat" })
     */
    const update = (
        changes: Partial<TicketRequest>,  // np. { body: "…" }
    ) => onChange({ ...ticket, ...changes });

    /**
     * Description:
     * Dopisuje nowy komentarz na koniec wątku z bieżącą chwilą i czyści jego szkic.
     *
     * Example args:
     *     (brak) — rola i treść ze stanu panelu
     *
     * Example result:
     *     undefined — wątek dłuższy o komentarz { role: "konsultant", created_at: "2026-10-20 10:15", … }
     */
    const addComment = () => {
        const comment: TicketComment = { role, body: body.trim(), created_at: formatTimestamp(new Date()) };

        update({ comments: [...ticket.comments, comment] });
        setBody("");
    };

    const examples = EXAMPLES.map((example, index) => ({ key: String(index), label: example.name }));

    return (
        <section className="column column-ticket" aria-label="Zgłoszenie">
            <div className="column-header">
                <h2>Zgłoszenie</h2>
                <Space>
                    <Dropdown menu={{ items: examples, onClick: ({ key }) => onChange(EXAMPLES[Number(key)].ticket) }}>
                        <Button>Przykłady <DownOutlined /></Button>
                    </Dropdown>
                    <Button onClick={() => onChange(EMPTY_TICKET)}>Wyczyść</Button>
                </Space>
            </div>

            <Space orientation="vertical" size={10} style={{ width: "100%" }}>
                <Space size={8} style={{ width: "100%" }}>
                    <Field label="Numer">
                        <Input value={ticket.ticket_id} onChange={(event) => update({ ticket_id: event.target.value })} />
                    </Field>
                    <Field label="Data">
                        <DatePicker
                            value={ticket.date === null ? null : dayjs(ticket.date, DATE_FORMAT)}
                            format={DATE_FORMAT}
                            placeholder="dziś"
                            style={{ width: "100%" }}
                            onChange={(value) => update({ date: value === null ? null : value.format(DATE_FORMAT) })}
                        />
                    </Field>
                </Space>
                <Field label="Temat">
                    <Input value={ticket.subject} onChange={(event) => update({ subject: event.target.value })} />
                </Field>
                <Field label="Treść">
                    <Input.TextArea
                        value={ticket.body}
                        rows={8}
                        style={RESIZABLE}
                        onChange={(event) => update({ body: event.target.value })}
                    />
                </Field>

                <div className="column-header" style={{ marginTop: 8, marginBottom: 0 }}>
                    <h2>Wątek</h2>
                    <span className="muted">{ticket.comments.length} kom.</span>
                </div>
                {ticket.comments.length === 0 ? (
                    <Empty description="Wątek bez komentarzy" />
                ) : (
                    <List
                        dataSource={ticket.comments}
                        renderItem={(comment, index) => (
                            <CommentItem
                                comment={comment}
                                onDelete={() => update({ comments: ticket.comments.filter((_, other) => other !== index) })}
                            />
                        )}
                    />
                )}

                <Space size={8} align="start" style={{ width: "100%" }}>
                    <Field label="Rola">
                        <Select value={role} onChange={setRole} options={ROLES.map((name) => ({ value: name, label: name }))} />
                    </Field>
                </Space>
                <Field label="Nowy komentarz">
                    <Input.TextArea value={body} rows={3} style={RESIZABLE} onChange={(event) => setBody(event.target.value)} />
                </Field>
                <Button icon={<PlusOutlined />} disabled={body.trim() === ""} onClick={addComment}>
                    Dodaj komentarz
                </Button>
            </Space>
        </section>
    );
}

/**
 * Description:
 * Pole formularza z podpisem nad nim; podpis jest etykietą pola dla czytników ekranu.
 *
 * Example args:
 *     label="Temat"
 *     children=<Input … />
 *
 * Example result:
 *     <label> z „Temat" i polem pod spodem
 */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 0 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{label}</Typography.Text>
            {children}
        </label>
    );
}

/**
 * Description:
 * Jeden komentarz wątku: rola, data, treść i guzik usunięcia.
 *
 * Example args:
 *     comment={ role: "klient", created_at: "2026-10-19 09:40", body: "Jedna pozycja…" }
 *     onDelete=() => …
 *
 * Example result:
 *     <List.Item> z „klient · 2026-10-19 09:40", treścią i koszem
 */
function CommentItem({ comment, onDelete }: { comment: TicketComment; onDelete: () => void }) {
    return (
        <List.Item
            actions={[
                <Button key="delete" type="text" size="small" icon={<DeleteOutlined />} aria-label="Usuń komentarz" onClick={onDelete} />,
            ]}
        >
            <Space orientation="vertical" size={2} style={{ width: "100%" }}>
                <Space size={8}>
                    <Tag color={comment.role === "klient" ? "blue" : "default"}>{comment.role || "bez roli"}</Tag>
                    <span className="muted">{comment.created_at}</span>
                </Space>
                <Typography.Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>{comment.body}</Typography.Paragraph>
            </Space>
        </List.Item>
    );
}
