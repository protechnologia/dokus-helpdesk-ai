-- Zapis zgłoszeń jednym poleceniem: lista wartości na kolumnę, w kolejności pól TicketRow.
-- Istniejący numer dostaje nowe dane; kolumny wyliczane baza przelicza sama.

INSERT INTO {table} (ticket_id, ticket_date, subject, thread)
SELECT * FROM unnest($1::text[], $2::date[], $3::text[], $4::text[])
ON CONFLICT (ticket_id) DO UPDATE SET
    ticket_date = EXCLUDED.ticket_date,
    subject     = EXCLUDED.subject,
    thread      = EXCLUDED.thread;
