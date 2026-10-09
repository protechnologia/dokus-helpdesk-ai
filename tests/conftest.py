"""
Description:
Wspólne zaplecze testów, które z hosta sięgają do działających usług: adresy usług i konfiguracja
aplikacji z tymi adresami. Leży w korzeniu `tests/`, bo potrzebują go testy integracyjne,
funkcjonalne i ewaluacyjne — różni je to, czego dowodzą, a nie sposób dotarcia do usługi.

Rodzaj testu to jego folder, a marker mówi, czego test potrzebuje do uruchomienia:

| marker           | czego wymaga                 | adres dla testu z hosta   |
|------------------|------------------------------|---------------------------|
| `stack`          | działającej usługi (parasol) | —                         |
| `stack_api`      | usługi `api`                 | `api_url()`               |
| `stack_qdrant`   | Qdranta                      | `qdrant_url()`            |
| `stack_embedder` | usługi `embedder`            | `embedder_url()`          |
| `stack_postgres` | Postgresa ze słownikiem      | `build_postgres_client()` |
| `llm_live`       | prawdziwego, płatnego modelu | — (z konfiguracji)        |

Marker nosi tylko test, który potrzebuje działającej usługi albo płatnego modelu. Jednostkowe nie
mają go nigdy, a w pozostałych rodzajach ma go mniejszość: większość testów integracyjnych
i funkcjonalnych chodzi w procesie, na plikach i atrapach. Test bez markera nie potrzebuje
niczego spoza repo i chodzi w domyślnym `pytest`.

O czym pamiętać przy zmianach:

- Markery rejestruje `pyproject.toml` i tam też domyślny przebieg je wyklucza (`addopts`). Nowy
  marker dopisuje się w rejestrze i w tej tabelce, a jeśli stoi poza parasolem `stack` — także
  w `addopts`.
- Test z markerem `stack_<usługa>` nosi też `stack`, żeby `-m stack` brał wszystko, co wymaga
  działającej usługi. `llm_live` stoi obok parasola celowo: `-m stack` nie może odpalić płatnego
  modelu.
- Komplet testów to `pytest -m "not llm_live"`. `pytest -m ""` zdejmuje wszystkie wykluczenia,
  więc wybiera też testy `llm_live`. Te biorą model przez `live_generation_llm()`, które przy
  takim wyborze odmawia: płatnego modelu nie da się zawołać bez wpisania `llm_live` w `-m`.
- Poza testami `llm_live` oba modele są atrapą, cokolwiek stoi w `.env`
  (`fake_models_outside_live_tests`). Fabryka grafów przy prawdziwym dostawcy składa graf na
  prawdziwym modelu, a zwykły test trasy nie może go zawołać ani zależeć od pliku dewelopera.
- Adresów nie wpisuje się w plikach testów. Konfiguracja wskazuje nazwy z sieci compose
  (`http://embedder:8000`), których z hosta nie da się rozwiązać, więc każdy test spoza kontenera
  potrzebuje podmiany; powielona w plikach rozjeżdżała się po zmianie portu w jednym miejscu.
- Każdy adres da się nadpisać zmienną środowiskową (`EMBEDDER_TEST_URL`, `QDRANT_TEST_URL`,
  `API_TEST_URL`, `POSTGRES_TEST_DSN`).
- Testy `llm_live` zgłaszają zużycie każdej sprawy przez fixture `live_usage`, a na końcu
  przebiegu pytest wypisuje je z sumą kosztu (`pytest_terminal_summary()`). Sam raport leży
  w `tests/helpers_live_usage.py`; tu zostają fixture i funkcja wypisująca, bo pytest szuka ich
  tylko w `conftest.py`.
"""

import os
from urllib.parse import urlsplit

import pytest
from _pytest.terminal import TerminalReporter  # pytest 8.3 nie wystawia tego typu pod `pytest.`

from app.config import LLMSettings, Settings
from app.db_postgres import PostgresClient
from tests.helpers_live_usage import LiveUsageReport

EMBEDDER_URL_ENV     = "EMBEDDER_TEST_URL"
EMBEDDER_URL_DEFAULT = "http://localhost:8001"

QDRANT_URL_ENV       = "QDRANT_TEST_URL"
QDRANT_URL_DEFAULT   = "http://localhost:6333"

# Zgodne z DOCKER_API_PORT w `.env.example`: 8000 bywa zajęte przez inny lokalny projekt, więc
# baza publikuje 8010.
API_URL_ENV     = "API_TEST_URL"
API_URL_DEFAULT = "http://localhost:8010"


# Zgodne z wartościami domyślnymi z compose: baza, użytkownik i hasło `helpdesk`, port hosta
# z DOCKER_POSTGRES_PORT. Przy własnych wartościach w `.env` test dostaje DSN przez zmienną.
POSTGRES_DSN_ENV     = "POSTGRES_TEST_DSN"
POSTGRES_DSN_DEFAULT = "postgresql://helpdesk:helpdesk@localhost:5433/helpdesk"

# Marker testów wołających prawdziwy, płatny model.
LLM_LIVE_MARKER = "llm_live"


def live_generation_llm(
    config: pytest.Config,  # np. request.config
) -> LLMSettings:
    """
    Description:
    Konfiguracja modelu generującego dla testów `llm_live` — jedyne wejście, przez które taki
    test bierze model. Odmawia w dwóch sytuacjach, w obu błędem, nie pominięciem:

    - testy wybrano bez jawnej prośby o żywy model, na przykład `pytest -m ""`, które zdejmuje
      wszystkie wykluczenia naraz — płatne wywołanie nie może być skutkiem ubocznym;
    - konfiguracja wskazuje atrapę modelu — zielony wynik bez ani jednego wywołania byłby
      fałszywy.

    Example args:
        config=request.config

    Example result:
        LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)

    Raises:
        AssertionError: wybór testów nie wymienia `llm_live` albo dostawcą jest `fake`
    """
    selected = config.getoption("markexpr")

    assert LLM_LIVE_MARKER in selected, (
        f"testy na żywym, płatnym modelu uruchamia się jawnie: -m {LLM_LIVE_MARKER} "
        f"(wybrano -m {selected!r}); komplet testów to -m 'not {LLM_LIVE_MARKER}'"
    )

    llm = Settings().llm_generation()

    assert llm.provider.strip().lower() != "fake", (
        f"testy {LLM_LIVE_MARKER} wymagają prawdziwego modelu, a LLM_GENERATION_PROVIDER wskazuje "
        f"atrapę — ustaw dostawcę, klucz i model w .env"
    )

    return llm


@pytest.fixture(autouse=True)
def fake_models_outside_live_tests(
    request:     pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie markery testu
    monkeypatch: pytest.MonkeyPatch,     # wstrzykiwane przez pytest; cofa zmienne po teście
) -> None:
    """
    Description:
    Ustawia oba modele na atrapę w każdym teście poza `llm_live`, niezależnie od pliku `.env`.

    Konfiguracja aplikacji czyta `.env` z katalogu roboczego, a tam deweloper trzyma prawdziwego
    dostawcę dla testów na żywym modelu. Fabryka grafów składa wtedy graf na prawdziwym modelu,
    więc zwykły test trasy albo wołałby płatny model, albo padał na odmowie anonimizatora —
    zależnie od tego, co akurat stoi w pliku. Zmienna środowiskowa wygrywa z `.env`, więc
    podmiana działa bez ruszania pliku. Test, który sprawdza innego dostawcę, ustawia go sam.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        None — `Settings()` w teście oddaje `fake` dla obu modeli
    """
    # --- test na żywym modelu ma czytać konfigurację dewelopera ---
    if request.node.get_closest_marker(LLM_LIVE_MARKER) is not None:
        return

    monkeypatch.setenv("LLM_GENERATION_PROVIDER", "fake")
    monkeypatch.setenv("LLM_ANONYMIZATION_PROVIDER", "fake")


# Miejsce raportu w konfiguracji przebiegu: fixture go tam wkłada, a podsumowanie stamtąd bierze.
LIVE_USAGE_KEY = pytest.StashKey[LiveUsageReport]()


@pytest.fixture(scope="session")
def live_usage(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> LiveUsageReport:
    """
    Description:
    Raport zużycia żywego modelu, jeden na cały przebieg pytesta. Test `llm_live` zgłasza w nim
    każdą sprawę, a po przebiegu pytest wypisuje podsumowanie z sumą kosztu.

    Raport bierze się wyłącznie przez tę fixture: klasę wolno zaimportować do opisu typu, ale
    obiekt zbudowany w teście byłby innym niż ten, z którego pytest wypisuje podsumowanie.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        LiveUsageReport wspólny dla wszystkich testów przebiegu
    """
    if LIVE_USAGE_KEY not in pytestconfig.stash:
        pytestconfig.stash[LIVE_USAGE_KEY] = LiveUsageReport()

    return pytestconfig.stash[LIVE_USAGE_KEY]


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,  # wstrzykiwane przez pytest; pisze na ekran
    config:           pytest.Config,     # wstrzykiwane przez pytest; trzyma raport
) -> None:
    """
    Description:
    Po przebiegu wypisuje zużycie żywego modelu: sprawy zgłoszone przez testy `llm_live`
    i sumę kosztu. Pytest woła tę funkcję sam, po nazwie. Gdy żaden test niczego nie zgłosił —
    czyli w każdym przebiegu bez żywego modelu — nie wypisuje nic.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        None — na końcu wyjścia pytesta stoi sekcja „zużycie żywego modelu"
    """
    report = config.stash.get(LIVE_USAGE_KEY, None)
    lines  = report.lines() if report is not None else []

    # --- przebieg bez żywego modelu ---
    if not lines:
        return

    terminalreporter.write_sep("=", "zużycie żywego modelu")

    for line in lines:
        terminalreporter.write_line(line)


def embedder_url() -> str:
    """
    Description:
    Adres, pod którym embedder odpowiada z hosta.

    Example args:
        (brak)

    Example result:
        "http://localhost:8001"
    """
    return os.environ.get(EMBEDDER_URL_ENV, EMBEDDER_URL_DEFAULT)


def qdrant_url() -> str:
    """
    Description:
    Adres, pod którym Qdrant odpowiada z hosta.

    Example args:
        (brak)

    Example result:
        "http://localhost:6333"
    """
    return os.environ.get(QDRANT_URL_ENV, QDRANT_URL_DEFAULT)


def api_url() -> str:
    """
    Description:
    Adres, pod którym usługa `api` odpowiada z hosta.

    Example args:
        (brak)

    Example result:
        "http://localhost:8010"
    """
    return os.environ.get(API_URL_ENV, API_URL_DEFAULT)


def postgres_dsn() -> str:
    """
    Description:
    Adres połączenia, pod którym Postgres odpowiada z hosta.

    Example args:
        (brak)

    Example result:
        "postgresql://helpdesk:helpdesk@localhost:5433/helpdesk"
    """
    return os.environ.get(POSTGRES_DSN_ENV, POSTGRES_DSN_DEFAULT)


def build_postgres_client(
    **overrides: object,  # np. password="zle-haslo" albo database="nie-ma-takiej"
) -> PostgresClient:
    """
    Description:
    Klient Postgresa połączony z bazą dostępną z hosta (`postgres_dsn()`). Argumenty nazwane
    podmieniają pojedyncze części adresu — tak test odtwarza złe hasło albo nieistniejącą bazę.

    Example args:
        overrides={"password": "zle-haslo"}

    Example result:
        PostgresClient dla localhost:5433/helpdesk ze złym hasłem
    """
    address = urlsplit(postgres_dsn())

    arguments = {
        "host":     address.hostname,
        "port":     address.port,
        "database": address.path.lstrip("/"),
        "user":     address.username,
        "password": address.password,
        **overrides,
    }

    client = PostgresClient(**arguments)

    return client


def build_host_settings() -> Settings:
    """
    Description:
    Konfiguracja aplikacji z adresami usług podmienionymi na dostępne z hosta. Reszta przychodzi
    ze środowiska bez zmian — progi, limity, nazwy kolekcji — więc test jedzie na konfiguracji,
    z jaką działa produkt, a podmienione są tylko dwa adresy, które poza siecią compose nie mają
    prawa zadziałać. Dostawcę modelu ustawia osobno `fake_models_outside_live_tests`.

    Funkcja obok fixture `host_settings`, bo fixture o zakresie modułu (jeden pomiar na cały plik)
    nie może użyć fixture o zakresie pojedynczego testu.

    Example args:
        (brak)

    Example result:
        Settings(embedding_base_url="http://localhost:8001", qdrant_url="http://localhost:6333", …)
    """
    settings = Settings(
        embedding_base_url = embedder_url(),
        qdrant_url         = qdrant_url(),
    )

    return settings


@pytest.fixture
def host_settings() -> Settings:
    """
    Description:
    Konfiguracja aplikacji z adresami usług dostępnymi z hosta (`build_host_settings()`).

    Example args:
        (brak)

    Example result:
        Settings(embedding_base_url="http://localhost:8001", qdrant_url="http://localhost:6333", …)
    """
    return build_host_settings()
