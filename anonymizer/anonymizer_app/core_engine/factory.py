import math
from functools import lru_cache

from anonymizer_app.agent_nodes.ask_model import prompt_chars
from anonymizer_app.agent_nodes.find_addresses import node as find_addresses
from anonymizer_app.agent_nodes.find_persons import node as find_persons
from anonymizer_app.agent_nodes.split_chunks.node import CHUNK_CHARS
from anonymizer_app.config import Settings, get_settings
from anonymizer_app.core_engine.agent import AGENT_ENGINE_NAME, AgentEngine
from anonymizer_app.core_engine.base import Engine
from anonymizer_app.core_engine.fake import FAKE_ENGINE_NAME, FakeEngine
from anonymizer_app.core_errors.engine_config_error import EngineConfigError
from anonymizer_app.core_service.analyzer_morphology import load_dictionary
from anonymizer_app.engine_llm import LLMClient

# Silniki, które ta wersja umie zbudować.
SUPPORTED_ENGINES = (FAKE_ENGINE_NAME, AGENT_ENGINE_NAME)

# Najmniej znaków na token, jakie dał tokenizer Bielika na wątkach korpusu (1,37; mediana 1,98,
# zmierzone 2026-10-19 na 1825 zgłoszeniach), z zapasem. Służy wyłącznie ODMOWIE startu: przy
# zbyt optymistycznej liczbie serwer odrzuciłby długą część błędem w środku żądania.
MIN_CHARS_PER_TOKEN = 1.3


def build_engine(
    settings: Settings,  # np. Settings(anonymization_engine="agent", …)
) -> Engine:
    """
    Description:
    Buduje silnik wskazany przez `ANONYMIZATION_ENGINE`. Nieznana nazwa albo niepełna konfiguracja
    kończą się błędem tutaj, przy budowie, więc usługa nie wstanie z silnikiem, który nie zadziała.

    Example args:
        settings=Settings(anonymization_engine="agent", llm_anonymization_base_url="https://…/v1",
                          llm_anonymization_model="speakleash/…")

    Example result:
        AgentEngine(…)

    Raises:
        EngineConfigError: nieznany silnik albo konfiguracja, z którą silnik `agent` nie zadziała
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje nie mogą wybierać silnika.
    engine = settings.anonymization_engine.strip().lower()

    if engine == FAKE_ENGINE_NAME:
        return FakeEngine()

    if engine == AGENT_ENGINE_NAME:
        return _build_agent_engine(settings)

    supported = ", ".join(SUPPORTED_ENGINES)

    raise EngineConfigError(
        f"nieznany ANONYMIZATION_ENGINE={settings.anonymization_engine!r}; dostępne: {supported}"
    )


def _build_agent_engine(
    settings: Settings,  # np. Settings(anonymization_engine="agent", …)
) -> AgentEngine:
    """
    Description:
    Buduje silnik `agent` po sprawdzeniu konfiguracji modelu: adres i nazwa modelu muszą być,
    a prompt z największą częścią tekstu i odpowiedzią — mieścić się w oknie serwera. Ładuje też
    słownik morfologiczny węzła osób.

    Example args:
        settings=Settings(anonymization_engine="agent", llm_anonymization_base_url="https://…/v1",
                          llm_anonymization_model="speakleash/…", llm_anonymization_num_ctx=16384)

    Example result:
        AgentEngine(…)

    Raises:
        EngineConfigError: brakuje adresu albo nazwy modelu, albo okno jest za małe
    """
    required = (
        ("LLM_ANONYMIZATION_BASE_URL", settings.llm_anonymization_base_url),
        ("LLM_ANONYMIZATION_MODEL",    settings.llm_anonymization_model),
    )

    missing = [name for name, value in required if not value]

    # Bez adresu nie ma dokąd wysłać tekstu, a domyślnego adresu celowo nie ma: ten model widzi
    # surowe zgłoszenia, więc dokąd one idą, ktoś musi wpisać świadomie.
    if missing:
        raise EngineConfigError(
            f"ANONYMIZATION_ENGINE={AGENT_ENGINE_NAME!r} wymaga ustawienia: {', '.join(missing)}"
        )

    _check_window(settings.llm_anonymization_num_ctx)

    # Słownik morfologiczny ładuje się tu, przy starcie (0,44 s): pierwsze zgłoszenie nie czeka,
    # a zepsuta instalacja słownika zatrzymuje usługę od razu, a nie w środku żądania.
    load_dictionary()

    llm = LLMClient(
        base_url    = settings.llm_anonymization_base_url,
        model       = settings.llm_anonymization_model,
        api_key     = settings.llm_anonymization_api_key,
        temperature = settings.llm_anonymization_temperature,
        timeout     = settings.llm_anonymization_timeout_seconds,
    )

    return AgentEngine(llm)


def _check_window(
    num_ctx: int,  # np. 16384 — okno serwera z LLM_ANONYMIZATION_NUM_CTX
) -> None:
    """
    Description:
    Odmawia startu, gdy któryś węzeł z modelem nie zmieści w oknie serwera promptu z przykładami,
    największej części tekstu i limitu odpowiedzi. Tokeny liczy pesymistycznie
    (`MIN_CHARS_PER_TOKEN`), bo to tylko odmowa: serwer, któremu wyślemy za dużo, odrzuci
    żądanie dopiero w trakcie pracy, a Ollama utnie je bez błędu.

    Example args:
        num_ctx=16384

    Example result:
        None  # wraca bez słowa, gdy oba węzły się mieszczą

    Raises:
        EngineConfigError: okno jest mniejsze niż to, czego potrzebuje któryś węzeł
    """
    # Węzły z modelem: katalog promptu, treść miejsc w prompcie i limit odpowiedzi każdego.
    model_nodes = (
        (
            find_persons.PROMPT_DIR,
            find_persons.prompt_values(find_persons.read_exceptions()),
            find_persons.MAX_ANSWER_TOKENS,
        ),
        (find_addresses.PROMPT_DIR, {}, find_addresses.MAX_ANSWER_TOKENS),
    )

    for prompt_dir, values, max_answer_tokens in model_nodes:
        needed = math.ceil((prompt_chars(prompt_dir, values) + CHUNK_CHARS) / MIN_CHARS_PER_TOKEN)
        needed += max_answer_tokens

        if needed > num_ctx:
            raise EngineConfigError(
                f"LLM_ANONYMIZATION_NUM_CTX={num_ctx} to za mało dla węzła {prompt_dir.name}: "
                f"prompt, część tekstu do {CHUNK_CHARS} znaków i odpowiedź potrzebują do "
                f"{needed} tokenów"
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
        AgentEngine(…)

    Raises:
        EngineConfigError: skonfigurowanego silnika nie da się zbudować
    """
    return build_engine(get_settings())
