-- Słownik i konfiguracja wyszukiwania pełnotekstowego dla języka polskiego.
--
-- Uruchamiane przez obraz TYLKO przy pierwszym starcie na pustym wolumenie. Zmiana tego pliku nie
-- dotrze do istniejącej bazy — trzeba ją zastosować ręcznie albo odtworzyć wolumen (dane
-- wyszukiwania odbudowują się z plików, zasada 8).
--
-- Kolejność słowników w mapowaniu ma znaczenie: `pl_ispell` sprowadza znane słowo do formy
-- podstawowej (serwerem -> serwer), a czego nie zna — kod błędu, nazwę własną spoza listy —
-- przejmuje `simple` i zostawia bez zmian, małymi literami.

CREATE TEXT SEARCH DICTIONARY pl_ispell (
    TEMPLATE = ispell,
    DictFile = polish,
    AffFile  = polish
);

CREATE TEXT SEARCH CONFIGURATION pl_search (COPY = simple);

ALTER TEXT SEARCH CONFIGURATION pl_search
    ALTER MAPPING FOR asciiword, word, hword_asciipart, hword_part
    WITH pl_ispell, simple;

-- Wyraz z łącznikiem wchodzi do indeksu wyłącznie jako części. Parser oddaje też całość
-- („e-doręczeń"), a ta nie jest w słowniku, więc zostałaby w odmienionej formie i zapytanie
-- „e-Doręczenia" wymagałoby jej dosłownie — czyli nie znalazłoby „e-Doręczeń".
ALTER TEXT SEARCH CONFIGURATION pl_search
    DROP MAPPING FOR asciihword, hword, numhword;
