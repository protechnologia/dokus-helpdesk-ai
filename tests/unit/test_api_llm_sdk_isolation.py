from pathlib import Path

import pytest

# One row per provider SDK: which modules may import it, and the import spellings that pull it in.
# Spellings are matched as substrings against source lines, which is coarse on purpose — a guard
# that only understood one spelling would miss the other (CLAUDE.md -> rule 4 and the "Don't" list).
#
# The OpenAI SDK has TWO allowed modules, not one: Ollama speaks the same protocol, so its client
# drives the same SDK against a local server. Both are transport clients, which is what rule 4
# permits — the rule bans the SDK from the DOMAIN, not from a second client.
SDK_RULES = (
    ("anthropic", ("import anthropic", "from anthropic"), ["llm/client_claude.py"]),
    ("openai",    ("import openai",    "from openai"),    ["llm/client_ollama.py",
                                                           "llm/client_openai.py"]),
)

APP_ROOT = Path(__file__).resolve().parents[2] / "api" / "app"


def _modules_importing(spellings: tuple[str, ...]) -> list[str]:
    """
    Description:
    Lists the modules under `api/app/` whose source contains one of the given import spellings, as
    paths relative to that root. Reads the files as TEXT rather than importing them: an import-based
    check would only see modules that happened to be loaded, and would miss exactly the accidental
    import this guard exists to catch.

    Example args:
        spellings=("import anthropic", "from anthropic")

    Example result:
        ["llm/client_claude.py"]
    """
    offenders = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")

        # Comment lines mentioning the SDK are prose, not a dependency.
        lines = [line.strip() for line in source.splitlines() if not line.strip().startswith("#")]

        if any(spelling in line for line in lines for spelling in spellings):
            offenders.append(str(path.relative_to(APP_ROOT)))

    return offenders


@pytest.mark.parametrize(("sdk", "spellings", "allowed_modules"), SDK_RULES)
def test_only_transport_clients_import_the_sdk(
    sdk:             str,               # e.g. "openai"
    spellings:       tuple[str, ...],   # e.g. ("import openai", "from openai")
    allowed_modules: list[str],         # e.g. ["llm/client_ollama.py", "llm/client_openai.py"]
):
    """SDK dostawcy importowany wyłącznie w klientach transportowych — domena go nie zna."""
    offenders = _modules_importing(spellings)

    assert offenders == sorted(allowed_modules), (
        f"SDK {sdk} zaimportowany poza {allowed_modules}: {offenders}. "
        f"Domena rozmawia z modelem wyłącznie przez LLMClient (CLAUDE.md -> zasada 4)."
    )


@pytest.mark.parametrize(("sdk", "spellings", "allowed_modules"), SDK_RULES)
def test_the_guard_actually_finds_the_import(
    sdk:             str,               # e.g. "openai"
    spellings:       tuple[str, ...],   # e.g. ("import openai", "from openai")
    allowed_modules: list[str],         # e.g. ["llm/client_ollama.py", "llm/client_openai.py"]
):
    """Strażnik widzi import w dozwolonych plikach — inaczej przechodziłby też po ich usunięciu."""
    # Bez tego asercja wyżej byłaby spełniona również przez pustą listę wynikającą z zepsutego
    # wyszukiwania, a test-strażnik milczałby o realnym złamaniu reguły.
    assert _modules_importing(spellings), f"strażnik nie znalazł importu SDK {sdk}"
