from functools import lru_cache

from anonymizer_app.config import Settings, get_settings
from anonymizer_app.engine.base import Engine
from anonymizer_app.engine.errors import EngineConfigError
from anonymizer_app.engine.fake import FAKE_ENGINE_NAME, FakeEngine

# Silniki, które ta wersja umie zbudować. Prawdziwy dochodzi w p. 19.4–19.5 (CLAUDE.md -> „Plan").
SUPPORTED_ENGINES = (FAKE_ENGINE_NAME,)


def build_engine(
    settings: Settings,  # np. Settings(anonymization_engine="fake")
) -> Engine:
    """
    Description:
    Buduje silnik wskazany przez `ANONYMIZATION_ENGINE`. Nieznana nazwa kończy się błędem tutaj,
    przy budowie, więc usługa nie wstanie z silnikiem, którego nie ma.

    Example args:
        settings=Settings(anonymization_engine="fake")

    Example result:
        FakeEngine()

    Raises:
        EngineConfigError: nieznany silnik
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje nie mogą wybierać silnika.
    engine = settings.anonymization_engine.strip().lower()

    if engine == FAKE_ENGINE_NAME:
        return FakeEngine()

    supported = ", ".join(SUPPORTED_ENGINES)

    raise EngineConfigError(
        f"nieznany ANONYMIZATION_ENGINE={settings.anonymization_engine!r}; dostępne: {supported}"
    )


@lru_cache
def get_engine() -> Engine:
    """
    Description:
    Silnik wspólny dla całego procesu, budowany raz. Osobno od `build_engine()`, żeby testy
    sprawdzały reguły konfiguracji bez ruszania zapamiętanej instancji.

    Example args:
        (brak)

    Example result:
        FakeEngine()

    Raises:
        EngineConfigError: skonfigurowanego silnika nie da się zbudować
    """
    return build_engine(get_settings())
