-- Zapis sekcji jednym poleceniem: lista wartości na kolumnę, w kolejności pól DocRow.
-- Istniejący identyfikator dostaje nowe dane; kolumny wyliczane baza przelicza sama.

INSERT INTO {table} (
    section_id, ordinal, document, version, released, chapter_path, title, description, body
)
SELECT * FROM unnest(
    $1::text[], $2::integer[], $3::text[], $4::text[], $5::date[], $6::text[],
    $7::text[], $8::text[], $9::text[]
)
ON CONFLICT (section_id) DO UPDATE SET
    ordinal      = EXCLUDED.ordinal,
    document     = EXCLUDED.document,
    version      = EXCLUDED.version,
    released     = EXCLUDED.released,
    chapter_path = EXCLUDED.chapter_path,
    title        = EXCLUDED.title,
    description  = EXCLUDED.description,
    body         = EXCLUDED.body;
