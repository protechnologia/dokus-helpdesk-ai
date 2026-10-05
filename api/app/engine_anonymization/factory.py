from app.config import Settings
from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.errors import AnonymizationConfigError
from app.engine_anonymization.fake import FakeAnonymizer


def build_anonymizer(
    settings: Settings,  # np. Settings(llm_generation_provider="fake")
) -> Anonymizer:
    """
    Description:
    Wybiera anonimizator z konfiguracji. Dziś jest tylko atrapa, a ta nie anonimizuje — więc
    przy prawdziwym modelu generującym fabryka odmawia startu, zamiast wypuścić surowy tekst do
    modelu zewnętrznego. Prawdziwy anonimizator dochodzi w p. 19 (CLAUDE.md -> „Plan").

    Rozstrzyga dostawca modelu GENERUJĄCEGO, bo to do niego idzie tekst po anonimizacji. Model
    anonimizujący (`LLM_ANONYMIZATION_*`) widzi surowy tekst z założenia i tu nie decyduje.

    Example args:
        settings=Settings(llm_generation_provider="fake")

    Example result:
        FakeAnonymizer()

    Raises:
        AnonymizationConfigError: `LLM_GENERATION_PROVIDER` inny niż `fake`, a prawdziwego
            anonimizatora nie ma
    """
    if settings.llm_generation_provider == "fake":
        return FakeAnonymizer()

    raise AnonymizationConfigError(
        f"LLM_GENERATION_PROVIDER={settings.llm_generation_provider} wymaga prawdziwego "
        f"anonimizatora, którego jeszcze nie ma — atrapa przepuszcza tekst bez zmian, więc "
        f"działa wyłącznie z LLM_GENERATION_PROVIDER=fake"
    )
