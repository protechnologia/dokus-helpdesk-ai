-- Tabela wyszukiwania tekstowego zgłoszeń: zgłoszenie w oryginalnym brzmieniu, po anonimizacji.
-- Karty zgłoszenia tu nie ma — karty trzyma baza wektorowa. {table} i {name} podstawia
-- TicketsTable (nazwa tabeli w cudzysłowie i bez niego).

CREATE TABLE IF NOT EXISTS {table} (
    ticket_id   text PRIMARY KEY,  -- numer zgłoszenia
    ticket_date date NOT NULL,     -- data zgłoszenia
    subject     text NOT NULL,     -- temat wycięty z wątku, tytuł na liście źródeł
    thread      text NOT NULL,     -- pełny tekst wątku po anonimizacji

    -- Przeszukiwany tekst: cały wątek. Kopia pod nazwą kolumny, w której szuka klasa bazowa tabel.
    search_text text GENERATED ALWAYS AS (thread) STORED,

    -- Słowa wątku po przejściu przez polski słownik.
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('pl_search', thread)) STORED
);

-- Indeks pełnotekstowy: słowa i fraza. Nazwa z przedrostkiem tabeli, bo musi być jedyna w bazie.
CREATE INDEX IF NOT EXISTS "{name}_search" ON {table} USING gin (search_vector);
