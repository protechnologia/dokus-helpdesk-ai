from app.config import Settings
from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.errors import AnonymizationConfigError
from app.engine_anonymization.fake import FakeAnonymizer


def build_anonymizer(
    settings: Settings,  # np. Settings(llm_provider="fake")
) -> Anonymizer:
    """
    Description:
    Wybiera anonimizator z konfiguracji. Dziś jest tylko atrapa, a ta nie anonimizuje — więc
    przy prawdziwym dostawcy LLM fabryka odmawia startu, zamiast wypuścić surowy tekst do modelu
    zewnętrznego. Prawdziwy anonimizator dochodzi w p. 19 (CLAUDE.md -> „Plan i TODO").

    Example args:
        settings=Settings(llm_provider="fake")

    Example result:
        FakeAnonymizer()

    Raises:
        AnonymizationConfigError: `LLM_PROVIDER` inny niż `fake`, a prawdziwego anonimizatora nie ma
    """
    if settings.llm_provider == "fake":
        return FakeAnonymizer()

    raise AnonymizationConfigError(
        f"LLM_PROVIDER={settings.llm_provider} wymaga prawdziwego anonimizatora, którego jeszcze "
        f"nie ma — atrapa przepuszcza tekst bez zmian, więc działa wyłącznie z LLM_PROVIDER=fake"
    )
