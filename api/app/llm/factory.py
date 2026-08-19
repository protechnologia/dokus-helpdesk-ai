from app.config import Settings
from app.llm.base import LLMClient
from app.llm.client_fake import FakeLLMClient
from app.llm.errors import LLMConfigError

# The vendor clients are imported INSIDE their builders, not here — the deliberate exception to
# "imports at the top" (CLAUDE.md -> "Styl kodu"), taken against a MEASURED problem.
#
# Why: `anthropic` takes ~5.5 s to import and `openai` ~3.3 s, because both build the Pydantic
# models of their entire API surface (every beta type, tool runner, streaming and Vertex layer) at
# import time. Importing all four clients in order to pick one made every importer of this module
# pay ~9 s for SDKs it would never call.
#
# What it actually buys, measured on collection alone: `tests/functional/` went 3.0 s -> 0.77 s
# (four times faster). It buys NOTHING for `tests/unit/` or a whole-repo run, where the client
# test files import the SDKs directly — that is their subject. So the win is on partial runs: a
# functional or integration pass, and `helpdesk` CLI commands that never touch a hosted provider.
#
# `FakeLLMClient` stays at the top: our own code, nothing heavy behind it, and the default provider.
# Cost accepted: the concrete client types cannot appear in the builders' signatures, so they
# return the `LLMClient` interface — which is what callers use anyway.

PROVIDER_FAKE   = "fake"
PROVIDER_CLAUDE = "claude"
PROVIDER_OPENAI = "openai"
PROVIDER_OLLAMA = "ollama"

# Separate entries, not one client with flags. `claude` differs in the SHAPE of the request
# (CLAUDE.md -> "Warstwa LLM"); `ollama` shares the OpenAI protocol but differs in everything
# around it — free, keyless, and slow enough that timeouts are measured in minutes.
SUPPORTED_PROVIDERS = (PROVIDER_FAKE, PROVIDER_CLAUDE, PROVIDER_OPENAI, PROVIDER_OLLAMA)

# Where Ollama listens when nothing says otherwise. A default rather than a required setting: the
# port is fixed by the tool, so demanding it in `.env` would be ceremony without a decision.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


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
) -> LLMClient:
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
    from app.llm.client_claude import ClaudeLLMClient

    _require_key_and_model(settings, PROVIDER_CLAUDE)

    return ClaudeLLMClient(
        api_key     = settings.llm_api_key,
        model       = settings.llm_model,
        timeout     = settings.llm_timeout_seconds,
        temperature = settings.llm_temperature,
    )


def _build_openai_client(
    settings: Settings,  # e.g. Settings(llm_provider="openai", llm_model="gpt-5.4-mini")
) -> LLMClient:
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
    from app.llm.client_openai import OpenAILLMClient

    _require_key_and_model(settings, PROVIDER_OPENAI)

    return OpenAILLMClient(
        api_key     = settings.llm_api_key,
        model       = settings.llm_model,
        base_url    = settings.llm_base_url,
        timeout     = settings.llm_timeout_seconds,
        temperature = settings.llm_temperature,
    )


def _build_ollama_client(
    settings: Settings,  # e.g. Settings(llm_provider="ollama", llm_model="bielik-4.5b:Q8_0")
) -> LLMClient:
    """
    Description:
    Builds the Ollama client. Only `LLM_MODEL` is required: a local server needs no API key, and its
    address has a working default — so this refuses to start on the ONE value it cannot guess.

    Example args:
        settings=Settings(llm_provider="ollama", llm_model="bielik-4.5b-v3.0-instruct:Q8_0")

    Example result:
        OllamaLLMClient(model="bielik-4.5b-v3.0-instruct:Q8_0", timeout=1800.0)

    Raises:
        LLMConfigError: `LLM_MODEL` is missing — there is no sensible default for which model to run
    """
    from app.llm.client_ollama import OllamaLLMClient

    if not settings.llm_model:
        raise LLMConfigError(f"LLM_PROVIDER={PROVIDER_OLLAMA!r} wymaga ustawienia: LLM_MODEL")

    return OllamaLLMClient(
        model             = settings.llm_model,
        base_url          = settings.llm_base_url or DEFAULT_OLLAMA_BASE_URL,
        timeout           = settings.llm_timeout_seconds,
        temperature       = settings.llm_temperature,
        num_ctx           = settings.llm_num_ctx,
        max_output_tokens = settings.llm_max_output_tokens,
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

    if provider == PROVIDER_OLLAMA:
        return _build_ollama_client(settings)

    supported = ", ".join(SUPPORTED_PROVIDERS)

    raise LLMConfigError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}; supported: {supported}")
