class EngineError(Exception):
    """
    Description:
    Wspólna klasa każdej awarii silnika anonimizacji. Trasa łapie ją, gdy wystarczy jej wiedzieć,
    że tekstu nie dało się zanonimizować — nigdy typów bibliotek, na których stoi silnik.
    """


class EngineConfigError(EngineError):
    """
    Description:
    Zgłaszany przy BUDOWIE silnika, gdy konfiguracja jest błędna (nieznany silnik). Celowo przy
    starcie: źle skonfigurowana usługa ma paść od razu, a nie przy pierwszym zgłoszeniu.
    """
