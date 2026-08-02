from pathlib import Path

import pytest

# One row per provider SDK: which module may import it, and the import spellings that pull it in.
# Spellings are matched as substrings against source lines, which is coarse on purpose — a guard
# that only understood one spelling would miss the other (CLAUDE.md -> rule 4 and the "Don't" list).
SDK_RULES = (
    ("llm/client_claude.py", ("import anthropic", "from anthropic")),
    ("llm/client_openai.py", ("import openai",    "from openai")),
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


@pytest.mark.parametrize(("allowed_module", "spellings"), SDK_RULES)
def test_only_its_own_client_imports_the_sdk(allowed_module: str, spellings: tuple[str, ...]):
    """SDK dostawcy importowany wyłącznie w jego kliencie — poza nim domena go nie zna."""
    offenders = _modules_importing(spellings)

    assert offenders == [allowed_module], (
        f"SDK zaimportowany poza {allowed_module}: {offenders}. "
        f"Domena rozmawia z modelem wyłącznie przez LLMClient (CLAUDE.md -> zasada 4)."
    )


@pytest.mark.parametrize(("allowed_module", "spellings"), SDK_RULES)
def test_the_guard_actually_finds_the_import(allowed_module: str, spellings: tuple[str, ...]):
    """Strażnik widzi import w dozwolonym pliku — inaczej przechodziłby też po jego usunięciu."""
    # Bez tego asercja wyżej byłaby spełniona również przez pustą listę wynikającą z zepsutego
    # wyszukiwania, a test-strażnik milczałby o realnym złamaniu reguły.
    assert _modules_importing(spellings), f"strażnik nie znalazł importu dla {allowed_module}"
