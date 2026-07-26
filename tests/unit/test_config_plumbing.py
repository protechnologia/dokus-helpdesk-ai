from pathlib import Path

from app.config import Settings

REPO_ROOT   = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _env_names_from_example() -> set[str]:
    """
    Description:
    Reads `.env.example` as DATA (no dotenv loading, no Docker) and returns the declared
    variable names. Values are irrelevant here — this file is a name contract.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL"}
    """
    names: set[str] = set()

    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # comments and blank lines carry no contract
        if not line or line.startswith("#"):
            continue
        # a line without "=" is malformed rather than a declaration
        if "=" not in line:
            continue
        names.add(line.split("=", 1)[0].strip())

    return names


def _env_names_from_settings() -> set[str]:
    """
    Description:
    Returns the ENV names `Settings` can consume, derived from its field names. The mapping is
    a plain upper-casing — `qdrant_url` is fed by `QDRANT_URL`.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL"}
    """
    return {field_name.upper() for field_name in Settings.model_fields}


def test_every_settings_field_is_declared_in_env_example() -> None:
    """Field present in Settings but missing from .env.example → fail (undocumented knob)."""
    missing = _env_names_from_settings() - _env_names_from_example()

    assert not missing, f"Missing in .env.example: {sorted(missing)}"


def test_every_env_example_entry_is_consumed_by_settings() -> None:
    """Variable declared in .env.example that Settings cannot read → fail (dead contract)."""
    unused = _env_names_from_example() - _env_names_from_settings()

    assert not unused, f"Declared in .env.example but unknown to Settings: {sorted(unused)}"
