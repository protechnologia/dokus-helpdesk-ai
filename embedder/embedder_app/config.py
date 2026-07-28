from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Description:
    Runtime knobs of the `embedder` service. Field names map to ENV names by upper-casing, and
    the names are the ones already declared in the project-wide `.env.example` — one contract
    for the whole compose project, not one per service (CLAUDE.md -> "Konfiguracja i deploy").

    Deliberately NOT reading a `.env` file: this service only ever receives plain `environment:`
    keys from compose. Dotenv is a convenience for `api`, which is also run from the repo root
    as a CLI; here it would only pretend to be configurable from a file that never ships.
    """

    model_config = SettingsConfigDict(
        extra          = "ignore",  # the shared environment carries keys other services own
        case_sensitive = False,
    )

    # --- observability ---
    log_level: str = "INFO"                             # e.g. "DEBUG"

    # --- vectors ---
    # `fake` keeps the service offline and instant: no weights, no GPU, no download. The real
    # backend arrives in stage 2; any other value fails fast with EncoderConfigError.
    embedding_backend:     str = "fake"                 # e.g. "local"
    # The dimension is a contract with the Qdrant collection, not a local detail.
    embedding_vector_size: int = 768                    # e.g. 1024

    @model_validator(mode="before")
    @classmethod
    def _drop_blank_values(cls, values: Any) -> Any:    # e.g. {"embedding_vector_size": " "}
        """
        Description:
        Drops keys whose value is an empty or whitespace-only string, so the field falls back to
        its default. `docker compose` substitutes an EMPTY STRING for an undefined `${VAR:-}`,
        which here would fail with an unreadable int-parsing error instead of simply defaulting.
        Duplicated from `api/app/config.py` on purpose: services share no code, only the ENV
        contract, and this trap bites every service that reads compose interpolation.

        Example args:
            values={"embedding_vector_size": "", "log_level": "DEBUG"}

        Example result:
            {"log_level": "DEBUG"}
        """
        # Sources normally hand over a dict; anything else is passed through untouched.
        if not isinstance(values, dict):
            return values

        return {
            key: value
            for key, value in values.items()
            if not (isinstance(value, str) and value.strip() == "")
        }


@lru_cache
def get_settings() -> Settings:
    """
    Description:
    Builds `Settings` once per process and hands the same instance to every request. Cached
    rather than module-level, so importing the module does not read the environment — and so a
    test can swap the value through FastAPI's dependency override.

    Example args:
        (none)

    Example result:
        Settings(log_level="INFO", embedding_vector_size=768)
    """
    return Settings()
