from pathlib import Path

# The single module allowed to import the provider SDK (CLAUDE.md -> rule 4 and the "Don't" list).
ALLOWED_MODULE = "client_claude.py"

# Import spellings that pull the SDK in. Matched as substrings against source lines, which is
# coarse on purpose: a guard that only understood one spelling would miss the other.
SDK_IMPORTS = ("import anthropic", "from anthropic")

APP_ROOT = Path(__file__).resolve().parents[2] / "api" / "app"


def _modules_importing_sdk() -> list[str]:
    """
    Description:
    Lists the modules under `api/app/` whose source imports the Anthropic SDK, as paths relative
    to that root. Reads the files as TEXT rather than importing them: an import-based check would
    only see modules that happened to be loaded, and would miss exactly the accidental import this
    guard exists to catch.

    Example args:
        (none)

    Example result:
        ["llm/client_claude.py"]
    """
    offenders = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")

        # Comment lines mentioning the SDK are prose, not a dependency.
        lines = [line.strip() for line in source.splitlines() if not line.strip().startswith("#")]

        if any(spelling in line for line in lines for spelling in SDK_IMPORTS):
            offenders.append(str(path.relative_to(APP_ROOT)))

    return offenders


def test_only_the_claude_client_imports_the_sdk():
    """SDK dostawcy importowany wyłącznie w kliencie — poza nim domena nie zna Anthropica."""
    offenders = _modules_importing_sdk()

    assert offenders == [f"llm/{ALLOWED_MODULE}"], (
        f"SDK Anthropic zaimportowany poza {ALLOWED_MODULE}: {offenders}. "
        f"Domena rozmawia z modelem wyłącznie przez LLMClient (CLAUDE.md -> zasada 4)."
    )


def test_the_guard_actually_finds_the_import():
    """Strażnik widzi import w dozwolonym pliku — inaczej przechodziłby też po jego usunięciu."""
    # Bez tego asercja wyżej byłaby spełniona również przez pustą listę wynikającą z zepsutego
    # wyszukiwania, a test-strażnik milczałby o realnym złamaniu reguły.
    assert _modules_importing_sdk(), "strażnik nie znalazł żadnego importu SDK — sprawdź wzorce"
