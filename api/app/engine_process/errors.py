class ProcessError(Exception):
    """
    Description:
    Program uruchomiony jako osobny proces nie dał wyniku: nie skończył w czasie albo zakończył
    się kodem, który u niego oznacza błąd.

    Do czego:
    Błąd bazowy pakietu `engine_process`, odpowiednik `EmbeddingError` i `DbPostgresError`.
    Wołający łapie ten jeden typ, gdy wystarczy mu wiedzieć, że wyniku nie ma. Do modelu nie
    wraca: inna fraza ani inna ścieżka niczego by nie zmieniły, więc przebieg staje, a trasa
    oddaje 503.

    Komunikat nazywa program i to, co się stało, bez argumentów wywołania: niosą tekst, którego
    szukał model, czyli treść zgłoszenia.
    """


class ProcessConfigError(ProcessError):
    """
    Description:
    Programu nie da się uruchomić wcale: nie ma go w systemie albo nie ma katalogu, w którym miał
    pracować.

    Błąd wdrożenia, nie stan przejściowy: czekanie go nie naprawi, więc handler błędów puszcza
    go dalej zamiast zamienić w 503, jak każdy błąd konfiguracji (CLAUDE.md -> „Logi
    i obserwowalność").
    """
