-- Tabela wyszukiwania tekstowego zgłoszeń: pole sparsowanego rekordu na kolumnę i pełny tekst
-- wątku. {table} i {name} podstawia TicketsTable (nazwa tabeli w cudzysłowie i bez niego).

CREATE TABLE IF NOT EXISTS {table} (
    ticket_id                     text    PRIMARY KEY,  -- numer zgłoszenia
    ticket_date                   date    NOT NULL,     -- data zgłoszenia
    component                     text    NOT NULL,     -- czego dotyczy sprawa
    problem                       text    NOT NULL,     -- zwięzły opis problemu
    symptoms                      text    NOT NULL,     -- objawy widziane przez użytkownika
    error_codes                   text    NOT NULL,     -- kody błędów, każdy w swojej linii
    cause                         text    NOT NULL,     -- ustalona przyczyna
    solution                      text    NOT NULL,     -- co rozwiązało sprawę
    resolution                    text    NOT NULL,     -- klasa rozstrzygnięcia ze słownika
    resolution_vocabulary_version integer NOT NULL,     -- wersja słownika rozstrzygnięć
    questions_summary             text    NOT NULL,     -- o co dopytywał konsultant
    thread                        text    NOT NULL,     -- pełny tekst wątku po anonimizacji

    -- Przeszukiwany tekst: sam wątek. Pola rekordu do niego nie wchodzą — to słowa parsera, nie
    -- zgłoszenia, a trafienie ma dać się wskazać w wątku. Kopia wątku pod nazwą kolumny, w której
    -- szuka klasa bazowa tabel.
    search_text text GENERATED ALWAYS AS (thread) STORED,

    -- Słowa wątku po przejściu przez polski słownik.
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('pl_search', thread)) STORED
);

-- Indeks pełnotekstowy: słowa i fraza. Nazwa z przedrostkiem tabeli, bo musi być jedyna w bazie.
CREATE INDEX IF NOT EXISTS "{name}_search" ON {table} USING gin (search_vector);
