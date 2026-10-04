class DbQdrantError(Exception):
    """
    Description:
    Wspólna klasa każdej awarii warstwy bazy wektorowej. Wołający łapie ją, gdy wystarczy mu
    wiedzieć „indeks nie odpowiedział" — nigdy typów `httpx`, które wyniosłyby transport do
    domeny (CLAUDE.md -> zasada 4).

    Osobna od `EmbeddingError`: to dwie różne granice procesu i dwie różne awarie. Niedostępny
    embedder znaczy, że wektory nie powstały; niedostępny Qdrant — że powstały, ale nie mają
    dokąd trafić. Przebieg indeksacji reaguje na nie inaczej.
    """


class DbQdrantConfigError(DbQdrantError):
    """
    Description:
    Zgłaszany przy BUDOWIE klienta albo kolekcji oraz wtedy, gdy to, co jest w Qdrancie, przeczy
    konfiguracji, z którą ma działać: inny wymiar wektora, brak nazwanego wektora, payload
    z innej wersji kontraktu.

    Żadnego z tych przypadków nie naprawi czekanie, więc nie mogą trafić do handlera 503, który
    znaczy „spróbuj za chwilę" (CLAUDE.md -> „Logi i obserwowalność"). Najważniejsze jest
    sprawdzenie wymiaru: bez niego rozjazd wychodzi jako odrzucone punkty godzinę w przebieg
    indeksacji, już po zapłaceniu za parsowanie LLM-em.
    """
