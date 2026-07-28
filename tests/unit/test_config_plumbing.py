from pathlib import Path

from pydantic_settings import BaseSettings

from app.config import Settings as ApiSettings
from embedder_app.config import Settings as EmbedderSettings

REPO_ROOT   = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# One `.env.example` is the contract for the WHOLE compose project, so the comparison must cover
# every service that reads it — not just `api`. A variable owned by another service (e.g.
# EMBEDDING_BACKEND) is a valid entry, and one owned by nobody is a dead entry.
SERVICE_SETTINGS: tuple[type[BaseSettings], ...] = (ApiSettings, EmbedderSettings)


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


def _env_names_from_settings(settings_class: type[BaseSettings]) -> set[str]:
    """
    Description:
    Returns the ENV names one service's `Settings` can consume, derived from its field names.
    The mapping is a plain upper-casing — `qdrant_url` is fed by `QDRANT_URL`.

    Example args:
        settings_class=ApiSettings

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL"}
    """
    return {field_name.upper() for field_name in settings_class.model_fields}


def _env_names_from_all_services() -> set[str]:
    """
    Description:
    Union of the ENV names every service can consume — the set of variables the project as a
    whole has a reader for.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL", "EMBEDDING_BACKEND"}
    """
    return set().union(*(_env_names_from_settings(cls) for cls in SERVICE_SETTINGS))


def test_every_settings_field_is_declared_in_env_example() -> None:
    """Field in any service's Settings but missing from .env.example → fail (undocumented knob)."""
    missing = _env_names_from_all_services() - _env_names_from_example()

    assert not missing, f"Missing in .env.example: {sorted(missing)}"


def test_every_env_example_entry_is_consumed_by_a_service() -> None:
    """Variable declared in .env.example that no service can read → fail (dead contract)."""
    unused = _env_names_from_example() - _env_names_from_all_services()

    assert not unused, f"Declared in .env.example but unknown to every service: {sorted(unused)}"


def test_services_agree_on_shared_variable_names() -> None:
    """Variable read by two services → same ENV name in both (a rename must not go half-way)."""
    shared = _env_names_from_settings(ApiSettings) & _env_names_from_settings(EmbedderSettings)

    # LOG_LEVEL and the vector width are deliberately shared: the dimension is one contract with
    # the Qdrant collection, so `api` and `embedder` must not drift into two names for it.
    assert {"LOG_LEVEL", "EMBEDDING_VECTOR_SIZE"} <= shared
