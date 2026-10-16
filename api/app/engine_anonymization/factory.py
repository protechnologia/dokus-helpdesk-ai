from app.config import Settings
from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.client import AnonymizerClient
from app.engine_anonymization.fake import FakeAnonymizer


def build_anonymizer(
    settings: Settings,  # np. Settings(llm_generation_provider="openai")
) -> Anonymizer:
    """
    Description:
    Wybiera anonimizator z konfiguracji. Przy atrapie modelu generującego nic nie wychodzi poza
    proces, więc wystarcza atrapa anonimizatora. Przy prawdziwym modelu fabryka buduje klienta
    usługi `anonymizer`; z niczym się przy tym nie łączy, a wyniku atrapy silnika usługi klient
    odmawia przy pierwszym wywołaniu.

    Rozstrzyga dostawca modelu GENERUJĄCEGO, bo to do niego idzie tekst po anonimizacji. Model
    anonimizujący (`LLM_ANONYMIZATION_*`) widzi surowy tekst z założenia i tu nie decyduje.

    Example args:
        settings=Settings(llm_generation_provider="openai")

    Example result:
        AnonymizerClient(base_url="http://anonymizer:8000")

    Raises:
        AnonymizationConfigError: pusty `ANONYMIZATION_BASE_URL` przy prawdziwym modelu
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje nie mogą wybierać drogi — tak samo
    # czytają ją fabryka grafów i fabryka klienta modelu.
    if settings.llm_generation_provider.strip().lower() == "fake":
        return FakeAnonymizer()

    client = AnonymizerClient(
        base_url = settings.anonymization_base_url,
        timeout  = settings.anonymization_timeout_seconds,
    )

    return client
