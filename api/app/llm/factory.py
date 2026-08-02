from app.config import Settings
from app.llm.base import LLMClient
from app.llm.client_claude import ClaudeLLMClient
from app.llm.client_fake import FakeLLMClient
from app.llm.client_openai import OpenAILLMClient
from app.llm.errors import LLMConfigError

PROVIDER_FAKE   = "fake"
PROVIDER_CLAUDE = "claude"
PROVIDER_OPENAI = "openai"

# Three entries, not two clients with a flag: the Messages API and the OpenAI API differ in the
# SHAPE of the request, not merely in the endpoint (CLAUDE.md -> "Warstwa LLM"). Bielik on RunPod
# will arrive through `openai` with a `base_url`, because its endpoint is OpenAI-compatible.
SUPPORTED_PROVIDERS = (PROVIDER_FAKE, PROVIDER_CLAUDE, PROVIDER_OPENAI)


def _require_key_and_model(
    settings: Settings,  # e.g. Settings(llm_provider="openai", llm_model="gpt-5.4-mini")
    provider: str,       # e.g. "openai" — named in the message, so the reader knows which one
) -> None:
    """
    Description:
    Refuses to build a hosted client without the two values every hosted provider needs. Both are
    optional in `Settings` (the default provider is offline and needs neither), so the requirement
    is enforced here — at the only point where it is real.

    Example args:
        settings=Settings(llm_provider="openai", llm_api_key="", llm_model="gpt-5.4-mini")
        provider="openai"

    Example result:
        None  # returns quietly when both values are present

    Raises:
        LLMConfigError: `LLM_API_KEY` or `LLM_MODEL` is missing
    """
    # Named separately so the message says WHICH value is missing — "configuration error" alone
    # sends the reader to the wrong half of the .env file.
    required = (
        ("LLM_API_KEY", settings.llm_api_key),
        ("LLM_MODEL",   settings.llm_model),
    )

    missing = [name for name, value in required if not value]

    if missing:
        raise LLMConfigError(f"LLM_PROVIDER={provider!r} wymaga ustawienia: {', '.join(missing)}")


def _build_claude_client(
    settings: Settings,  # e.g. Settings(llm_provider="claude", llm_model="claude-haiku-4-5")
) -> ClaudeLLMClient:
    """
    Description:
    Builds the Claude client, checking first that the configuration it needs is present.

    Example args:
        settings=Settings(llm_provider="claude", llm_api_key="sk-ant-…",
                          llm_model="claude-haiku-4-5")

    Example result:
        ClaudeLLMClient(model="claude-haiku-4-5", timeout=60.0)

    Raises:
        LLMConfigError: `LLM_API_KEY` or `LLM_MODEL` is missing, or the model has no known price
    """
    _require_key_and_model(settings, PROVIDER_CLAUDE)

    return ClaudeLLMClient(
        api_key     = settings.llm_api_key,
        model       = settings.llm_model,
        timeout     = settings.llm_timeout_seconds,
        temperature = settings.llm_temperature,
    )


def _build_openai_client(
    settings: Settings,  # e.g. Settings(llm_provider="openai", llm_model="gpt-5.4-mini")
) -> OpenAILLMClient:
    """
    Description:
    Builds the OpenAI client. `LLM_BASE_URL` stays optional on purpose: empty means the official
    API, set means an OpenAI-compatible endpoint (Bielik on RunPod, Ollama, vLLM) — which is the
    whole reason this provider is not tied to one host.

    Example args:
        settings=Settings(llm_provider="openai", llm_api_key="sk-proj-…",
                          llm_model="gpt-5.4-mini")

    Example result:
        OpenAILLMClient(model="gpt-5.4-mini", timeout=60.0)

    Raises:
        LLMConfigError: `LLM_API_KEY` or `LLM_MODEL` is missing, or the model has no known price
    """
    _require_key_and_model(settings, PROVIDER_OPENAI)

    return OpenAILLMClient(
        api_key     = settings.llm_api_key,
        model       = settings.llm_model,
        base_url    = settings.llm_base_url,
        timeout     = settings.llm_timeout_seconds,
        temperature = settings.llm_temperature,
    )


def get_llm_client(settings: Settings) -> LLMClient:   # e.g. Settings(llm_provider="fake")
    """
    Description:
    Builds the LLM client named by `LLM_PROVIDER`. Fails fast: an unknown provider, or a real one
    lacking its key or model, raises here at construction time instead of surfacing as a
    connection error in the middle of a request.

    Example args:
        settings=Settings(llm_provider="fake")

    Example result:
        FakeLLMClient()

    Raises:
        LLMConfigError: `LLM_PROVIDER` names a provider this build does not implement, or the
            named provider is missing configuration it requires
    """
    # ENV values arrive as typed by a human: case and stray spaces must not decide the provider.
    provider = settings.llm_provider.strip().lower()

    if provider == PROVIDER_FAKE:
        return FakeLLMClient()

    if provider == PROVIDER_CLAUDE:
        return _build_claude_client(settings)

    if provider == PROVIDER_OPENAI:
        return _build_openai_client(settings)

    supported = ", ".join(SUPPORTED_PROVIDERS)

    raise LLMConfigError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}; supported: {supported}")
