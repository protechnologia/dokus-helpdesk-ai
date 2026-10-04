-- Tabela wyszukiwania tekstowego dokumentacji: opis sekcji z metryczki, miejsce w dokumencie
-- i treść. {table} i {name} podstawia DocsTable (nazwa tabeli w cudzysłowie i bez niego).

CREATE TABLE IF NOT EXISTS {table} (
    section_id   text    PRIMARY KEY,  -- identyfikator sekcji z metryczki
    ordinal      integer NOT NULL,     -- kolejność sekcji w dokumencie
    document     text    NOT NULL,     -- tytuł dokumentu
    version      text    NOT NULL,     -- wydanie dokumentu
    released     date,                 -- data wydania; bywa nieznana
    chapter_path text    NOT NULL,     -- ścieżka rozdziału, lista tytułów w JSON-ie
    title        text    NOT NULL,     -- tytuł sekcji
    description  text    NOT NULL,     -- krótki opis sekcji z metryczki
    body         text    NOT NULL,     -- treść pliku .md sekcji

    -- Przeszukiwany tekst: tytuł sekcji i jej treść. Opis z metryczki pisze model przy
    -- przygotowaniu plików, a trafienie ma wynikać z oryginału — dlatego go tu nie ma.
    search_text text GENERATED ALWAYS AS (title || E'\n' || body) STORED,

    -- Słowa tego samego tekstu po przejściu przez polski słownik. Wyrażenie musi być powtórzone:
    -- kolumna wyliczana nie może czytać innej kolumny wyliczanej.
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('pl_search', title || E'\n' || body)
    ) STORED
);

-- Indeks pełnotekstowy: słowa i fraza. Nazwa z przedrostkiem tabeli, bo musi być jedyna w bazie.
CREATE INDEX IF NOT EXISTS "{name}_search" ON {table} USING gin (search_vector);
