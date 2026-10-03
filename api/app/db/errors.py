class DbError(Exception):
    """
    Description:
    Wspólna klasa każdej awarii warstwy bazy. Wołający łapie ją, gdy wystarczy mu wiedzieć „baza
    nie odpowiedziała" — nigdy typów sterownika, które wyniosłyby transport do domeny
    (CLAUDE.md -> zasada 4).

    Osobna od `RetrievalError`: to dwie różne usługi i dwie różne awarie. Niedostępny Qdrant
    wyłącza wyszukiwanie po znaczeniu, niedostępny Postgres — po dosłownym brzmieniu, a agent
    mający oba narzędzia może dalej pracować jednym.
    """


class DbConfigError(DbError):
    """
    Description:
    Zgłaszany przy BUDOWIE klienta albo gdy baza przeczy konfiguracji, z którą ma działać: brak
    hasła, odrzucone hasło, nieistniejąca baza, brak konfiguracji wyszukiwania `pl_search`.

    Żadnego z tych przypadków nie naprawi czekanie, więc nie mogą trafić do handlera 503, który
    znaczy „spróbuj za chwilę" (CLAUDE.md -> „Logi i obserwowalność").
    """
