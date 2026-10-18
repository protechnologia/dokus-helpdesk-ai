from anonymizer_app.errors.engine_error import EngineError


class EngineConfigError(EngineError):
    """
    Description:
    Zgłaszany przy BUDOWIE silnika, gdy konfiguracja jest błędna (nieznany silnik). Celowo przy
    starcie: źle skonfigurowana usługa ma paść od razu, a nie przy pierwszym zgłoszeniu.
    """
