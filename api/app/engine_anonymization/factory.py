from app.config import Settings
from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.client import AnonymizerClient


def build_anonymizer(
    settings: Settings,  # np. Settings(llm_generation_provider="openai")
) -> Anonymizer:
    """
    Description:
    Buduje anonimizator z konfiguracji: zawsze klienta usługi `anonymizer`, bo o tym, czy usługa
    działa na atrapie silnika, decyduje jej własna konfiguracja (`ANONYMIZATION_ENGINE`), nie
    `api`. Z niczym się przy tym nie łączy.

    Fabryka rozstrzyga tylko, czy klient może przyjąć wynik atrapy silnika: tak przy atrapie
    modelu generującego, bo tekst nie trafia wtedy do żadnego modelu; nie przy prawdziwym —
    tam klient odmawia przy pierwszym wywołaniu. Rozstrzyga dostawca modelu GENERUJĄCEGO, bo to
    do niego idzie tekst po anonimizacji. Model anonimizujący konfiguruje usługa `anonymizer`.

    Example args:
        settings=Settings(llm_generation_provider="openai")

    Example result:
        AnonymizerClient(base_url="http://anonymizer:8000"), bez zgody na atrapę silnika

    Raises:
        AnonymizationConfigError: pusty `ANONYMIZATION_BASE_URL`
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje nie mogą wybierać drogi — tak samo
    # czytają ją fabryka grafów i fabryka klienta modelu.
    fake_model = settings.llm_generation_provider.strip().lower() == "fake"

    client = AnonymizerClient(
        base_url            = settings.anonymization_base_url,
        fake_engine_allowed = fake_model,
        timeout             = settings.anonymization_timeout_seconds,
    )

    return client
