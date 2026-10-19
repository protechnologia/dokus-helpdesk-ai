from anonymizer_app.core_errors.engine_error import EngineError


class EngineConfigError(EngineError):
    """
    Description:
    Zgłaszany przy BUDOWIE silnika, gdy konfiguracja jest błędna (nieznany silnik, brak adresu
    albo nazwy modelu, okno kontekstu za małe na prompt). Celowo przy starcie: źle
    skonfigurowana usługa ma paść od razu, a nie przy pierwszym zgłoszeniu.

    Jedyny wyjątek od „przy starcie": odmowa modelu, która znaczy złą konfigurację (nieznany model,
    odrzucony klucz). Usługa przy starcie z modelem się nie łączy, bo endpoint z GPU bywa
    chwilowo wyłączony, więc to wychodzi dopiero przy pierwszym wywołaniu — także jako ten błąd,
    nie jako 503, bo czekanie go nie naprawi.
    """
