import pytest

from anonymizer_app.config import Settings
from anonymizer_app.engine import EngineConfigError, EngineError, FakeEngine, build_engine


@pytest.mark.parametrize("engine", ["fake", " Fake "])
def test_the_default_engine_is_the_fake(engine: str) -> None:
    """Sprawdza, czy domyślna konfiguracja i wartość `ANONYMIZATION_ENGINE` „fake", także wpisana
    jako „ Fake ", dają atrapę silnika.

    Wyłapuje usługę, która bez ustawienia nie wstaje albo czyta nazwę silnika zależnie od
    wielkości liter i spacji, które wpisał człowiek."""
    assert isinstance(build_engine(Settings()), FakeEngine)
    assert isinstance(build_engine(Settings(anonymization_engine=engine)), FakeEngine)


def test_an_unknown_engine_fails_at_build_time() -> None:
    """Sprawdza, czy nieznana nazwa silnika kończy budowę błędem konfiguracji
    `EngineConfigError`, który podaje błędną wartość i dostępne silniki.

    Wyłapuje usługę, która z literówką w nazwie silnika wstaje i pada dopiero przy pierwszym
    zgłoszeniu, albo komunikat, który nie mówi, co poprawić."""
    with pytest.raises(EngineConfigError) as caught:
        build_engine(Settings(anonymization_engine="ner"))

    assert "'ner'" in str(caught.value)
    assert "fake"  in str(caught.value)


def test_a_config_error_is_an_engine_error() -> None:
    """Sprawdza, czy błąd konfiguracji silnika jest odmianą ogólnego błędu silnika
    (`EngineError`).

    Wyłapuje rozdzielenie tych klas: handler usługi łapie `EngineError` i musi rozpoznać w nim
    błąd konfiguracji, żeby nie zamienić go na uprzejme 503."""
    assert issubclass(EngineConfigError, EngineError)
