class DbPostgresError(Exception):
    """
    Description:
    Wspólna klasa każdej awarii warstwy bazy. Wołający łapie ją, gdy wystarczy mu wiedzieć „baza
    nie odpowiedziała" — nigdy typów sterownika, które wyniosłyby transport do domeny
    (CLAUDE.md -> zasada 4).

    Osobna od `DbQdrantError`: to dwie różne usługi i dwie różne awarie. Niedostępny Qdrant
    wyłącza wyszukiwanie po znaczeniu, niedostępny Postgres — po dosłownym brzmieniu, a agent
    mający oba narzędzia może dalej pracować jednym.
    """


class DbPostgresConfigError(DbPostgresError):
    """
    Description:
    Zgłaszany przy BUDOWIE klienta albo gdy baza przeczy konfiguracji, z którą ma działać: brak
    hasła, odrzucone hasło, nieistniejąca baza, brak konfiguracji wyszukiwania `pl_search`,
    brak tabeli (`DbPostgresMissingTableError`).

    Żadnego z tych przypadków nie naprawi czekanie, więc nie mogą trafić do handlera 503, który
    znaczy „spróbuj za chwilę" (CLAUDE.md -> „Logi i obserwowalność").
    """


class DbPostgresMissingTableError(DbPostgresConfigError):
    """
    Description:
    Zgłaszany, gdy zapytanie sięga do tabeli, której w bazie nie ma, czyli gdy indeksu tego
    materiału nikt nie zbudował.

    Pusta tabela błędem nie jest: oddaje pusty wynik. Brak tabeli jest, bo pusty wynik w jego
    miejscu wyglądałby jak „materiał nic o tym nie mówi" i nikt by nie zauważył, że indeksu nie
    ma. Dziedziczy po błędzie konfiguracji, więc kończy żądanie głośno, a nie jako 503.
    """
