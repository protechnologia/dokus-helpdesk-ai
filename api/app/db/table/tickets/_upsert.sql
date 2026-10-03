-- Zapis zgłoszeń jednym poleceniem: lista wartości na kolumnę, w kolejności pól TicketRow.
-- Istniejący numer dostaje nowe dane; kolumny wyliczane baza przelicza sama.

INSERT INTO {table} (
    ticket_id, ticket_date, component, problem, symptoms, error_codes,
    cause, solution, resolution, resolution_vocabulary_version, questions_summary, thread
)
SELECT * FROM unnest(
    $1::text[], $2::date[], $3::text[], $4::text[], $5::text[], $6::text[],
    $7::text[], $8::text[], $9::text[], $10::integer[], $11::text[], $12::text[]
)
ON CONFLICT (ticket_id) DO UPDATE SET
    ticket_date                   = EXCLUDED.ticket_date,
    component                     = EXCLUDED.component,
    problem                       = EXCLUDED.problem,
    symptoms                      = EXCLUDED.symptoms,
    error_codes                   = EXCLUDED.error_codes,
    cause                         = EXCLUDED.cause,
    solution                      = EXCLUDED.solution,
    resolution                    = EXCLUDED.resolution,
    resolution_vocabulary_version = EXCLUDED.resolution_vocabulary_version,
    questions_summary             = EXCLUDED.questions_summary,
    thread                        = EXCLUDED.thread;
