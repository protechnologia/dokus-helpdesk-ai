import pytest

from embedder_app.config import Settings
from embedder_app.encoding import EncoderConfigError, EncoderError, FakeEncoder, build_encoder
from embedder_app.encoding.factory import _verify_dimension


def _settings(
    backend:     str,       # e.g. "fake"
    vector_size: int = 768,
    model:       str = "",  # e.g. "OPI-PIB/PolDense-150M"
) -> Settings:
    """
    Description:
    Builds Settings with an explicit backend, so the assertions cannot be moved by a variable
    exported in the developer's shell (an init argument outranks the environment).

    Example args:
        backend="fake"
        vector_size=768
        model=""

    Example result:
        Settings(embedding_backend="fake", embedding_vector_size=768)
    """
    return Settings(
        embedding_backend     = backend,
        embedding_model       = model,
        embedding_vector_size = vector_size,
    )


def test_default_backend_builds_the_offline_fake() -> None:
    """Sprawdza, czy przy `EMBEDDING_BACKEND=fake`, czyli wartości domyślnej w kodzie usługi,
    fabryka buduje atrapę kodera (`FakeEncoder`), która działa bez wag modelu.

    Wyłapuje fabrykę, która dla tej wartości buduje coś innego albo odmawia: testy i start usługi
    bez pobranego modelu przestałyby działać offline."""
    encoder = build_encoder(_settings("fake"))

    assert isinstance(encoder, FakeEncoder)


def test_backend_name_is_read_case_and_space_insensitively() -> None:
    """Sprawdza, czy nazwa backendu wpisana wielkimi literami i ze zbędnymi spacjami na początku
    i na końcu („FAKE" zamiast „fake") daje tę samą atrapę kodera.

    Wyłapuje fabrykę, która porównuje nazwę znak w znak: wartość w `.env` wpisuje człowiek, więc
    wielkość liter ani zbędna spacja nie mogą decydować o tym, czy usługa wstanie."""
    encoder = build_encoder(_settings("  FAKE "))

    assert isinstance(encoder, FakeEncoder)


def test_encoder_is_built_with_the_configured_dimension() -> None:
    """Sprawdza, czy atrapa kodera zbudowana przez fabrykę ma wymiar wektora z konfiguracji: przy
    `EMBEDDING_VECTOR_SIZE=1024` zgłasza 1024.

    Wyłapuje fabrykę, która nie przekazuje atrapie skonfigurowanego wymiaru. Atrapa nie ma modelu,
    który mógłby go zmierzyć, więc bez tego oddawałaby wektory innej długości, niż ustawiono."""
    encoder = build_encoder(_settings("fake", vector_size=1024))

    assert encoder.dimension == 1024


def test_unimplemented_backend_fails_at_build_time() -> None:
    """Sprawdza, czy nazwa backendu, którego usługa nie obsługuje („onnx"), kończy budowę kodera
    wyjątkiem `EncoderConfigError`.

    Wyłapuje fabrykę, która nieznaną nazwę przepuszcza albo po cichu zastępuje innym backendem:
    usługa ma paść przy starcie, a nie dopiero przy pierwszym żądaniu o wektory."""
    with pytest.raises(EncoderConfigError):
        build_encoder(_settings("onnx"))


def test_config_error_names_the_offending_value() -> None:
    """Sprawdza, czy komunikat błędu o nieznanym backendzie zawiera odrzuconą wartość, tutaj
    „poldense".

    Wyłapuje komunikat, który mówi tylko, że konfiguracja jest zła: osoba uruchamiająca usługę nie
    widziałaby wtedy, którą wartość w `.env` ma poprawić."""
    with pytest.raises(EncoderConfigError, match="poldense"):
        build_encoder(_settings("poldense"))


def test_config_error_is_catchable_as_the_layer_error() -> None:
    """Sprawdza, czy błąd konfiguracji kodera da się złapać jako ogólny błąd tej warstwy,
    `EncoderError`: budowa kodera z nieznanym backendem zgłasza wyjątek tego typu.

    Wyłapuje rozdzielenie obu wyjątków: wołający, który jednym typem łapie każdą awarię liczenia
    wektorów, przestałby wtedy widzieć błędy konfiguracji."""
    with pytest.raises(EncoderError):
        build_encoder(_settings("onnx"))


def test_real_backend_without_a_model_name_fails_at_build_time() -> None:
    """Sprawdza, czy backend `sentence-transformers` bez podanej nazwy modelu kończy budowę kodera
    wyjątkiem `EncoderConfigError`, który wymienia zmienną `EMBEDDING_MODEL`.

    Wyłapuje fabrykę, która z pustą nazwą próbuje ładować model: błąd przyszedłby wtedy
    z biblioteki, przy pobieraniu wag, i nie mówiłby, której zmiennej brakuje."""
    with pytest.raises(EncoderConfigError, match="EMBEDDING_MODEL"):
        build_encoder(_settings("sentence-transformers"))


def test_real_backend_rejects_a_whitespace_only_model_name() -> None:
    """Sprawdza, czy nazwa modelu złożona z samych spacji jest traktowana jak brak nazwy: budowa
    kodera kończy się wyjątkiem `EncoderConfigError`, który wymienia `EMBEDDING_MODEL`.

    Wyłapuje fabrykę, która uznaje spacje za nazwę i próbuje pobrać model o takiej nazwie, zamiast
    od razu wskazać pustą zmienną."""
    with pytest.raises(EncoderConfigError, match="EMBEDDING_MODEL"):
        build_encoder(_settings("sentence-transformers", model="   "))


# The dimension check reads two properties and nothing else, so `FakeEncoder` — which is TOLD its
# width — stands in for the real model here. Loading weights to assert on an integer would make a
# unit test download hundreds of megabytes.
def test_dimension_mismatch_is_refused_at_build_time() -> None:
    """Sprawdza, czy koder zwracający wektory o wymiarze 768 jest odrzucany wyjątkiem
    `EncoderConfigError`, gdy konfiguracja mówi o wymiarze 1024.

    Wyłapuje kontrolę wymiaru, która taką niezgodność przepuszcza. Rozjazd wyszedłby wtedy dopiero
    jako odrzucenie punktów przez Qdranta w środku indeksacji, już po opłaconym parsowaniu zgłoszeń
    modelem."""
    with pytest.raises(EncoderConfigError):
        _verify_dimension(FakeEncoder(dimension=768), expected=1024)


def test_dimension_mismatch_message_names_both_numbers() -> None:
    """Sprawdza, czy komunikat o niezgodnym wymiarze podaje obie liczby: wymiar kodera (768)
    i wymiar z konfiguracji (1024).

    Wyłapuje komunikat bez którejś z liczb: czytający nie wiedziałby wtedy, czy poprawić
    `EMBEDDING_VECTOR_SIZE`, czy wybrać inny model."""
    with pytest.raises(EncoderConfigError, match="768.*1024"):
        _verify_dimension(FakeEncoder(dimension=768), expected=1024)


def test_matching_dimension_passes_quietly() -> None:
    """Sprawdza, czy koder o wymiarze zgodnym z konfiguracją (768 i 768) przechodzi kontrolę wymiaru
    bez wyjątku.

    Wyłapuje kontrolę, która odrzuca także poprawną parę, na przykład przez odwrócony warunek:
    usługa z dobrze ustawionym modelem w ogóle by nie wstała."""
    _verify_dimension(FakeEncoder(dimension=768), expected=768)
