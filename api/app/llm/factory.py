from app.config import Settings
from app.llm.base import LLMClient
from app.llm.errors import LLMConfigError
from app.llm.fake import FakeLLMClient

PROVIDER_FAKE = "fake"

# Only the offline fake exists so far. A real, OpenAI-compatible client (cloud on dev, Bielik on
# RunPod on prod) joins the tuple in stage 5, when the first caller appears — the abstraction is
# here earlier so nobody imports a provider SDK straight into the domain in the meantime.
SUPPORTED_PROVIDERS = (PROVIDER_FAKE,)


def get_llm_client(settings: Settings) -> LLMClient:   # e.g. Settings(llm_provider="fake")
    """
    Description:
    Builds the LLM client named by `LLM_PROVIDER`. Fails fast: an unknown provider (or, later, a
    real one lacking its key/model/base URL) raises here, at construction time, instead of
    surfacing as a connection error inside a request.

    Example args:
        settings=Settings(llm_provider="fake")

    Example result:
        FakeLLMClient()

    Raises:
        LLMConfigError: `LLM_PROVIDER` names a provider this build does not implement
    """
    # ENV values arrive as typed by a human: case and stray spaces must not decide the provider.
    provider = settings.llm_provider.strip().lower()

    if provider == PROVIDER_FAKE:
        return FakeLLMClient()

    supported = ", ".join(SUPPORTED_PROVIDERS)

    raise LLMConfigError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}; supported: {supported}")
