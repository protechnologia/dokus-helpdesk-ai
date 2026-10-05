-- Tabela wyszukiwania tekstowego zgłoszeń: zgłoszenie w oryginalnym brzmieniu, po anonimizacji.
-- Karty zgłoszenia tu nie ma — karty trzyma baza wektorowa. {table} i {name} podstawia
-- TicketsTable (nazwa tabeli w cudzysłowie i bez niego).

CREATE TABLE IF NOT EXISTS {table} (
    ticket_id   text PRIMARY KEY,  -- numer zgłoszenia
    ticket_date date NOT NULL,     -- data zgłoszenia
    subject     text NOT NULL,     -- temat wycięty z wątku, tytuł na liście źródeł
    thread      text NOT NULL,     -- pełny tekst wątku po anonimizacji

    -- Przeszukiwany tekst: cały wątek, pod nazwą kolumny, w której szuka klasa bazowa tabel.
    -- Każdy ciąg białych znaków, także twarda spacja, staje się jedną spacją: komunikat złamany
    -- w wątku między liniami ma być do znalezienia w całości. Wątek w `thread` zostaje dosłowny.
    search_text text GENERATED ALWAYS AS (
        regexp_replace(thread, '[\s\u00A0]+', ' ', 'g')
    ) STORED,

    -- Słowa wątku po przejściu przez polski słownik.
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('pl_search', thread)) STORED
);

-- Indeks pełnotekstowy: słowa i fraza. Nazwa z przedrostkiem tabeli, bo musi być jedyna w bazie.
CREATE INDEX IF NOT EXISTS "{name}_search" ON {table} USING gin (search_vector);
