"""
Description:
Wspólne zaplecze testów, które z hosta sięgają do działających usług: adresy usług i konfiguracja
aplikacji z tymi adresami. Leży w korzeniu `tests/`, bo potrzebują go testy integracyjne,
funkcjonalne i ewaluacyjne — różni je to, czego dowodzą, a nie sposób dotarcia do usługi.

Rodzaj testu to jego folder, a marker mówi, czego test potrzebuje do uruchomienia:

| marker             | czego wymaga                 | adres dla testu z hosta   |
|--------------------|------------------------------|---------------------------|
| `stack`            | działającej usługi (parasol) | —                         |
| `stack_api`        | usługi `api`                 | `api_url()`               |
| `stack_qdrant`     | Qdranta                      | `qdrant_url()`            |
| `stack_embedder`   | usługi `embedder`            | `embedder_url()`          |
| `stack_anonymizer` | usługi `anonymizer`          | `anonymizer_url()`        |
| `stack_postgres`   | Postgresa ze słownikiem      | `build_postgres_client()` |
| `llm_live`         | prawdziwego, płatnego modelu | — (z konfiguracji)        |

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
- Poza testami na stacku fabryka grafów dostaje `FakeAnonymizer` zamiast klienta usługi
  `anonymizer` (`fake_anonymizer_outside_stack_tests`). Klienta buduje przy każdym dostawcy,
  a domyślny przebieg usługi nie ma. Test samej drogi fabryki przywraca `build_anonymizer`.
- Adresów nie wpisuje się w plikach testów. Konfiguracja wskazuje nazwy z sieci compose
  (`http://embedder:8000`), których z hosta nie da się rozwiązać, więc każdy test spoza kontenera
  potrzebuje podmiany; powielona w plikach rozjeżdżała się po zmianie portu w jednym miejscu.
- Każdy adres da się nadpisać zmienną środowiskową (`EMBEDDER_TEST_URL`, `ANONYMIZER_TEST_URL`,
  `QDRANT_TEST_URL`, `API_TEST_URL`, `POSTGRES_TEST_DSN`).
- Testy `llm_live` zgłaszają zużycie każdej sprawy przez fixture `live_usage`, a na końcu
  przebiegu pytest wypisuje je z sumą kosztu (`pytest_terminal_summary()`). Sam raport leży
  w `tests/_helpers/live/`; tu zostają fixture i funkcja wypisująca, bo pytest szuka ich
  tylko w `conftest.py`. Tak samo raporty scenariuszy: fixture `<scenariusz>_report`
  (`injection_report`, `gate_report`, `polish_report`, `questions_report`, `code_report`,
  `solution_report`, `reading_report`), a klasa raportu
  w `tests/_helpers/scenarios/<scenariusz>/`; po przebiegu stoją przed zużyciem modelu.
"""

import os
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from _pytest.terminal import TerminalReporter  # pytest 8.3 nie wystawia tego typu pod `pytest.`

from app.agent_graphs import factory as graph_factory
from app.config import Settings
from app.db_postgres import PostgresClient
from app.engine_anonymization import FakeAnonymizer
from tests._helpers.live import LLM_LIVE_MARKER, LiveUsageReport
from tests._helpers.scenarios.code import CodeReport
from tests._helpers.scenarios.gates import GateReport
from tests._helpers.scenarios.injections import InjectionReport
from tests._helpers.scenarios.polish import PolishReport
from tests._helpers.scenarios.questions import QuestionsReport
from tests._helpers.scenarios.reading import ReadingReport
from tests._helpers.scenarios.solution import SolutionReport

# Parasol testów, które potrzebują działającej usługi: tylko one rozmawiają z prawdziwym
# anonimizatorem.
STACK_MARKER = "stack"

EMBEDDER_URL_ENV     = "EMBEDDER_TEST_URL"
EMBEDDER_URL_DEFAULT = "http://localhost:8001"

# Zgodne z DOCKER_ANONYMIZER_PORT w `.env.example`.
ANONYMIZER_URL_ENV     = "ANONYMIZER_TEST_URL"
ANONYMIZER_URL_DEFAULT = "http://localhost:8002"

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


@pytest.fixture(autouse=True)
def fake_anonymizer_outside_stack_tests(
    request:     pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie markery testu
    monkeypatch: pytest.MonkeyPatch,     # wstrzykiwane przez pytest; cofa podmianę po teście
) -> Iterator[None]:
    """
    Description:
    Podstawia fabryce grafów `FakeAnonymizer` w każdym teście poza testami na stacku.

    Fabryka buduje klienta usługi `anonymizer` przy każdym dostawcy modelu, także przy atrapie,
    bo w czasie działania `api` nie ma własnej atrapy tej usługi. Domyślny przebieg usługi nie
    ma, więc bez podmiany każdy test trasy grafu kończyłby się błędem połączenia. Anonimizator
    jest zapamiętywany na cały proces, więc pamięć fabryki czyści się przed testem i po nim.
    Test, który sprawdza samą drogę fabryki, przywraca `build_anonymizer` sam.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        None — `process_anonymizer()` w teście oddaje `FakeAnonymizer`
    """
    # --- test na stacku ma rozmawiać z prawdziwą usługą ---
    if request.node.get_closest_marker(STACK_MARKER) is not None:
        yield

        return

    monkeypatch.setattr(graph_factory, "build_anonymizer", lambda settings: FakeAnonymizer())
    graph_factory.process_anonymizer.cache_clear()

    yield

    graph_factory.process_anonymizer.cache_clear()


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


# Miejsce raportu wstrzyknięć w konfiguracji przebiegu, na tej samej zasadzie co raport zużycia.
INJECTION_REPORT_KEY = pytest.StashKey[InjectionReport]()


@pytest.fixture(scope="session")
def injection_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> InjectionReport:
    """
    Description:
    Raport scenariuszy wstrzyknięć, jeden na cały przebieg pytesta. Test wstrzyknięć zgłasza
    w nim ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem z polami wyniku.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        InjectionReport wspólny dla wszystkich testów przebiegu
    """
    if INJECTION_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[INJECTION_REPORT_KEY] = InjectionReport()

    return pytestconfig.stash[INJECTION_REPORT_KEY]


# Miejsce raportu bramek w konfiguracji przebiegu, na tej samej zasadzie co raport zużycia.
GATE_REPORT_KEY = pytest.StashKey[GateReport]()


@pytest.fixture(scope="session")
def gate_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> GateReport:
    """
    Description:
    Raport scenariuszy bramek, jeden na cały przebieg pytesta. Test bramek zgłasza w nim ocenę
    każdej sprawy, a po przebiegu pytest wypisuje ją razem z polami werdyktu.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        GateReport wspólny dla wszystkich testów przebiegu
    """
    if GATE_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[GATE_REPORT_KEY] = GateReport()

    return pytestconfig.stash[GATE_REPORT_KEY]


# Miejsce raportu „Popraw” w konfiguracji przebiegu, na tej samej zasadzie co raport zużycia.
POLISH_REPORT_KEY = pytest.StashKey[PolishReport]()


@pytest.fixture(scope="session")
def polish_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> PolishReport:
    """
    Description:
    Raport scenariuszy „Popraw”, jeden na cały przebieg pytesta. Test „Popraw” zgłasza w nim
    ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem z poprawionym tekstem.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        PolishReport wspólny dla wszystkich testów przebiegu
    """
    if POLISH_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[POLISH_REPORT_KEY] = PolishReport()

    return pytestconfig.stash[POLISH_REPORT_KEY]


# Miejsce raportu pytań w konfiguracji przebiegu, na tej samej zasadzie co raport zużycia.
QUESTIONS_REPORT_KEY = pytest.StashKey[QuestionsReport]()


@pytest.fixture(scope="session")
def questions_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> QuestionsReport:
    """
    Description:
    Raport scenariuszy „pytań już nie trzeba”, jeden na cały przebieg pytesta. Test pytań
    zgłasza w nim ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem z pytaniami
    i uwagami.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        QuestionsReport wspólny dla wszystkich testów przebiegu
    """
    if QUESTIONS_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[QUESTIONS_REPORT_KEY] = QuestionsReport()

    return pytestconfig.stash[QUESTIONS_REPORT_KEY]



# Miejsce raportu cytowania kodu w konfiguracji przebiegu, na tej samej zasadzie co raport zużycia.
CODE_REPORT_KEY = pytest.StashKey[CodeReport]()


@pytest.fixture(scope="session")
def code_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> CodeReport:
    """
    Description:
    Raport scenariuszy cytowania kodu, jeden na cały przebieg pytesta. Test cytowania kodu
    zgłasza w nim ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem z licznikami
    i uwagami dla wdrożeniowca.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        CodeReport wspólny dla wszystkich testów przebiegu
    """
    if CODE_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[CODE_REPORT_KEY] = CodeReport()

    return pytestconfig.stash[CODE_REPORT_KEY]

# Miejsce raportu scenariuszy rozwiązania w konfiguracji przebiegu, na tej samej zasadzie co raport
# zużycia.
SOLUTION_REPORT_KEY = pytest.StashKey[SolutionReport]()


@pytest.fixture(scope="session")
def solution_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> SolutionReport:
    """
    Description:
    Raport scenariuszy rozwiązania, jeden na cały przebieg pytesta. Test rozwiązania zgłasza
    w nim ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem z licznikami i treścią
    propozycji.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        SolutionReport wspólny dla wszystkich testów przebiegu
    """
    if SOLUTION_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[SOLUTION_REPORT_KEY] = SolutionReport()

    return pytestconfig.stash[SOLUTION_REPORT_KEY]


# Miejsce raportu scenariuszy czytania w konfiguracji przebiegu, na tej samej zasadzie co raport
# zużycia.
READING_REPORT_KEY = pytest.StashKey[ReadingReport]()


@pytest.fixture(scope="session")
def reading_report(
    pytestconfig: pytest.Config,  # wstrzykiwane przez pytest; trzyma raport na cały przebieg
) -> ReadingReport:
    """
    Description:
    Raport scenariuszy czytania znalezionego materiału, jeden na cały przebieg pytesta. Test
    czytania zgłasza w nim ocenę każdej sprawy, a po przebiegu pytest wypisuje ją razem
    z licznikami i polami wyniku.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        ReadingReport wspólny dla wszystkich testów przebiegu
    """
    if READING_REPORT_KEY not in pytestconfig.stash:
        pytestconfig.stash[READING_REPORT_KEY] = ReadingReport()

    return pytestconfig.stash[READING_REPORT_KEY]


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,  # wstrzykiwane przez pytest; pisze na ekran
    config:           pytest.Config,     # wstrzykiwane przez pytest; trzyma raporty
) -> None:
    """
    Description:
    Po przebiegu wypisuje raporty testów na żywym modelu: najpierw oceny spraw ze scenariuszy
    wstrzyknięć, bramek, „Popraw”, pytań, cytowania kodu, rozwiązania i czytania z polami
    wyniku, potem zużycie żywego modelu z sumą kosztu. Pytest woła tę funkcję sam, po nazwie.
    Raport, do którego żaden test niczego nie zgłosił — czyli każdy w przebiegu bez żywego
    modelu — nie wypisuje nic.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        None — na końcu wyjścia pytesta stoją sekcje „wstrzyknięcia poleceń", „scenariusze
        bramek", „scenariusze »Popraw«", „scenariusze pytań", „scenariusze cytowania kodu",
        „scenariusze rozwiązania", „scenariusze czytania" i „zużycie żywego modelu"
    """
    sections = [
        ("wstrzyknięcia poleceń",        config.stash.get(INJECTION_REPORT_KEY, None)),
        ("scenariusze bramek",           config.stash.get(GATE_REPORT_KEY, None)),
        ("scenariusze „Popraw”",         config.stash.get(POLISH_REPORT_KEY, None)),
        ("scenariusze pytań",            config.stash.get(QUESTIONS_REPORT_KEY, None)),
        ("scenariusze cytowania kodu",   config.stash.get(CODE_REPORT_KEY, None)),
        ("scenariusze rozwiązania",      config.stash.get(SOLUTION_REPORT_KEY, None)),
        ("scenariusze czytania",         config.stash.get(READING_REPORT_KEY, None)),
        ("zużycie żywego modelu",        config.stash.get(LIVE_USAGE_KEY, None)),
    ]

    for title, report in sections:
        lines = report.lines() if report is not None else []

        # --- raport bez zgłoszonych spraw ---
        if not lines:
            continue

        terminalreporter.write_sep("=", title)

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


def anonymizer_url() -> str:
    """
    Description:
    Adres, pod którym usługa `anonymizer` odpowiada z hosta.

    Example args:
        (brak)

    Example result:
        "http://localhost:8002"
    """
    return os.environ.get(ANONYMIZER_URL_ENV, ANONYMIZER_URL_DEFAULT)


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
