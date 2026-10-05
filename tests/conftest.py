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
- Adresów nie wpisuje się w plikach testów. Konfiguracja wskazuje nazwy z sieci compose
  (`http://embedder:8000`), których z hosta nie da się rozwiązać, więc każdy test spoza kontenera
  potrzebuje podmiany; powielona w plikach rozjeżdżała się po zmianie portu w jednym miejscu.
- Każdy adres da się nadpisać zmienną środowiskową (`EMBEDDER_TEST_URL`, `QDRANT_TEST_URL`,
  `API_TEST_URL`, `POSTGRES_TEST_DSN`).
"""

import os
from urllib.parse import urlsplit

import pytest

from app.config import LLMSettings, Settings
from app.db_postgres import PostgresClient

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
    Konfiguracja aplikacji z adresami usług podmienionymi na dostępne z hosta. Cała reszta
    przychodzi ze środowiska bez zmian — przede wszystkim dostawca LLM — więc test jedzie na
    konfiguracji, z jaką działa produkt, a podmienione są tylko dwa adresy, które poza siecią
    compose nie mają prawa zadziałać.

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
