from app.config import LLMSettings
from app.engine_llm.base import LLMClient
from app.engine_llm.client.fake import FakeLLMClient
from app.engine_llm.errors import LLMConfigError

# Klienci dostawców są importowani WEWNĄTRZ builderów, nie tutaj — świadomy wyjątek od „importy na
# górze" (CLAUDE.md -> „Styl kodu"), wzięty na ZMIERZONY problem.
#
# Powód: `anthropic` importuje się ok. 5,5 s, a `openai` ok. 3,3 s, bo oba budują przy imporcie
# modele Pydantic całego swojego API (typy beta, tool runner, streaming, Vertex). Import wszystkich
# klientów po to, żeby wybrać jednego, kazał każdemu importerowi tego modułu płacić ok. 9 s za
# biblioteki, których nie zawoła.
#
# Co to daje, zmierzone na samej kolekcji testów: `tests/functional/` 3,0 s -> 0,77 s. Dla
# `tests/unit/` i dla całego repo zysku NIE MA: pliki testów klientów importują SDK wprost, bo to
# ich przedmiot. Zysk dotyczy przebiegów częściowych i komend CLI niesięgających do dostawcy.
#
# `FakeLLMClient` zostaje na górze: nasz kod, nic ciężkiego pod spodem, dostawca domyślny.
# Cena: buildery nie mogą mieć w sygnaturze konkretnej klasy klienta, więc zwracają interfejs
# `LLMClient` — a tego i tak używa wołający.

PROVIDER_FAKE   = "fake"
PROVIDER_CLAUDE = "claude"
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"

# Osobne wpisy, a nie jeden klient z flagami. `claude` różni się KSZTAŁTEM żądania (CLAUDE.md ->
# „Warstwa LLM"); `ollama` mówi protokołem OpenAI, ale różni się wszystkim dookoła — jest darmowy,
# bez klucza i tak wolny, że limity czasu liczy się w minutach.
SUPPORTED_PROVIDERS = (PROVIDER_FAKE, PROVIDER_CLAUDE, PROVIDER_OPENAI, PROVIDER_OLLAMA)

# Gdzie nasłuchuje Ollama, gdy nic nie mówi inaczej. Wartość domyślna, a nie wymagane ustawienie:
# port ustala samo narzędzie, więc żądanie go w `.env` byłoby ceremonią bez decyzji.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


def _require_key_and_model(
    llm:      LLMSettings,  # np. LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
    provider: str,          # np. "openai" — do komunikatu, żeby było wiadomo, o którego chodzi
) -> None:
    """
    Description:
    Odmawia budowy klienta dostawcy chmurowego bez dwóch wartości, których każdy taki dostawca
    potrzebuje. Obie są w konfiguracji opcjonalne (dostawca domyślny jest offline i nie potrzebuje
    żadnej), więc wymóg jest egzekwowany tutaj — w jedynym miejscu, w którym jest prawdziwy.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", api_key=None,
                        model="gpt-5.4-mini", …)
        provider="openai"

    Example result:
        None  # wraca bez słowa, gdy obie wartości są

    Raises:
        LLMConfigError: brakuje klucza albo nazwy modelu tej roli
    """
    # Nazwane osobno i z przedrostkiem roli, żeby komunikat mówił, KTÓREJ zmiennej brakuje:
    # przy dwóch konfiguracjach samo „brak klucza" odsyła do złej połowy pliku `.env`.
    required = (
        (f"{llm.env_prefix}API_KEY", llm.api_key),
        (f"{llm.env_prefix}MODEL",   llm.model),
    )

    missing = [name for name, value in required if not value]

    if missing:
        raise LLMConfigError(
            f"{llm.env_prefix}PROVIDER={provider!r} wymaga ustawienia: {', '.join(missing)}"
        )


def _build_claude_client(
    llm: LLMSettings,  # np. LLMSettings(provider="claude", model="claude-haiku-4-5", …)
) -> LLMClient:
    """
    Description:
    Buduje klienta Claude'a, sprawdzając najpierw, czy jest konfiguracja, której potrzebuje.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="claude", api_key="sk-ant-…",
                        model="claude-haiku-4-5", …)

    Example result:
        ClaudeLLMClient(model="claude-haiku-4-5", timeout=60.0)

    Raises:
        LLMConfigError: brakuje klucza albo nazwy modelu, albo model nie ma ceny w cenniku
    """
    from app.engine_llm.client.claude import ClaudeLLMClient

    _require_key_and_model(llm, PROVIDER_CLAUDE)

    return ClaudeLLMClient(
        api_key     = llm.api_key,
        model       = llm.model,
        timeout     = llm.timeout_seconds,
        temperature = llm.temperature,
    )


def _build_openai_client(
    llm: LLMSettings,  # np. LLMSettings(provider="openai", model="gpt-5.4-mini", …)
) -> LLMClient:
    """
    Description:
    Buduje klienta OpenAI. Adres (`base_url`) jest opcjonalny: pusty oznacza oficjalne API,
    ustawiony — pośrednika, który mówi API Responses. Endpointy zgodne z OpenAI (Ollama, vLLM,
    RunPod) mówią Chat Completions i idą przez dostawcę `ollama`.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", api_key="sk-proj-…",
                        model="gpt-5.4-mini", …)

    Example result:
        OpenAILLMClient(model="gpt-5.4-mini", timeout=60.0)

    Raises:
        LLMConfigError: brakuje klucza albo nazwy modelu, albo model nie ma ceny w cenniku
    """
    from app.engine_llm.client.openai import OpenAILLMClient

    _require_key_and_model(llm, PROVIDER_OPENAI)

    return OpenAILLMClient(
        api_key     = llm.api_key,
        model       = llm.model,
        base_url    = llm.base_url,
        timeout     = llm.timeout_seconds,
        temperature = llm.temperature,
    )


def _build_ollama_client(
    llm: LLMSettings,  # np. LLMSettings(provider="ollama", model="bielik-4.5b:Q8_0", …)
) -> LLMClient:
    """
    Description:
    Buduje klienta Ollamy. Wymagana jest tylko nazwa modelu: lokalny serwer nie potrzebuje
    klucza, a jego adres ma działającą wartość domyślną — fabryka odmawia więc na JEDYNEJ
    wartości, której nie da się zgadnąć.

    Example args:
        llm=LLMSettings(env_prefix="LLM_ANONYMIZATION_", provider="ollama",
                        model="bielik-4.5b-v3.0-instruct:Q8_0", …)

    Example result:
        OllamaLLMClient(model="bielik-4.5b-v3.0-instruct:Q8_0", timeout=60.0)

    Raises:
        LLMConfigError: brakuje nazwy modelu — nie ma sensownej wartości domyślnej
    """
    from app.engine_llm.client.ollama import OllamaLLMClient

    if not llm.model:
        raise LLMConfigError(
            f"{llm.env_prefix}PROVIDER={PROVIDER_OLLAMA!r} wymaga ustawienia: "
            f"{llm.env_prefix}MODEL"
        )

    return OllamaLLMClient(
        model             = llm.model,
        env_prefix        = llm.env_prefix,
        base_url          = llm.base_url or DEFAULT_OLLAMA_BASE_URL,
        timeout           = llm.timeout_seconds,
        temperature       = llm.temperature,
        num_ctx           = llm.num_ctx,
        max_output_tokens = llm.max_output_tokens,
    )


def get_llm_client(
    llm: LLMSettings,  # np. Settings().llm_generation()
) -> LLMClient:
    """
    Description:
    Buduje klienta modelu z jednego kompletu ustawień — tego samego kodu używają obie role:
    model generujący (`Settings().llm_generation()`) i model anonimizujący
    (`Settings().llm_anonymization()`). Którą rolę klient obsłuży, rozstrzyga wołający tym, który
    komplet poda.

    Fail-fast: nieznany dostawca albo prawdziwy dostawca bez klucza czy modelu kończy się błędem
    tutaj, przy budowie, a nie błędem połączenia w środku żądania.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="fake", …)

    Example result:
        FakeLLMClient()

    Raises:
        LLMConfigError: nieznany dostawca albo dostawcy brakuje wymaganej konfiguracji
    """
    # Wartości z ENV wpisuje człowiek: wielkość liter i zbędne spacje nie mogą wybierać dostawcy.
    provider = llm.provider.strip().lower()

    if provider == PROVIDER_FAKE:
        return FakeLLMClient()

    if provider == PROVIDER_CLAUDE:
        return _build_claude_client(llm)

    if provider == PROVIDER_OPENAI:
        return _build_openai_client(llm)

    if provider == PROVIDER_OLLAMA:
        return _build_ollama_client(llm)

    supported = ", ".join(SUPPORTED_PROVIDERS)

    raise LLMConfigError(
        f"nieznany {llm.env_prefix}PROVIDER={llm.provider!r}; obsługiwane: {supported}"
    )
