from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Description:
    Single source of truth for every runtime knob of the `api` service. Values come from the
    environment only (see CLAUDE.md -> rule 1); nothing here may be hardcoded at a call site.

    Flow:
        1. pydantic-settings collects values from the process environment (and `.env` on the
           host, which is a developer convenience — containers get plain `environment:` keys).
        2. `_drop_blank_values` removes keys whose value is an empty or whitespace-only string,
           so a blank from `docker compose` falls back to the default declared here instead of
           silently becoming `""`.
        3. Field types and defaults apply; a missing required value fails fast at construction.

    Field names map to ENV names by upper-casing: `qdrant_url` <- `QDRANT_URL`. The prefixes
    (`LLM_`, `EMBEDDING_`, `QDRANT_`) are the only namespacing — there is one `.env` for the
    whole compose project, not one per service.
    """

    model_config = SettingsConfigDict(
        env_file       = ".env",  # host convenience only; resolved relative to the CWD
        extra          = "ignore",  # a shared .env holds keys other services care about
        case_sensitive = False,
    )

    # --- observability ---
    log_level: str = "INFO"                             # e.g. "DEBUG"

    # --- LLM: defaults to the offline fake, so `up` and `pytest` cost nothing ---
    llm_provider:        str        = "fake"            # e.g. "openai"
    llm_base_url:        str | None = None              # e.g. "https://api.openai.com/v1"
    llm_api_key:         str | None = None              # e.g. "sk-proj-...HNkA"
    llm_model:           str | None = None              # e.g. "gpt-4o-mini"
    llm_temperature:     float      = 0.0               # 0 for every extraction task
    llm_timeout_seconds: float      = 60.0              # seconds

    # Context budget, in tokens. Hosted providers manage their own window and ignore both values;
    # they exist for self-hosted runners (Ollama, vLLM), where the window is OUR decision and a
    # wrong one is silent — anything past `llm_num_ctx` is dropped without an error.
    # Both belong in ENV rather than in code because they depend on the model and the machine:
    # the same client serves a 4.5B model on a laptop and Bielik 11B on a rented GPU.
    llm_num_ctx:           int = 8192                   # must fit what the model declares
    llm_max_output_tokens: int = 1500                   # carved OUT of llm_num_ctx, not added

    # --- embedder service (own compose service, reached over REST) ---
    embedding_base_url:        str   = "http://embedder:8000"
    embedding_vector_size:     int   = 768              # must match the Qdrant collection
    # Sized for the SLOWEST call — an indexing batch against a cold model, not a runtime query.
    embedding_timeout_seconds: float = 120.0            # seconds

    # --- Qdrant ---
    qdrant_url:              str   = "http://qdrant:6333"
    qdrant_collection:       str   = "tickets"
    qdrant_timeout_seconds:  float = 30.0               # seconds

    # --- retrieval: tuning, NOT business logic ---
    # These two are knobs a deployment turns; the rules that read them are not. Scoring the hits
    # and mapping a score onto a suggested variant stay in code, because that is a judgement about
    # answer quality rather than a setting (CLAUDE.md -> "Konfiguracja i deploy").
    #
    # Top 5 because more dilutes the answer: the generation prompt is built from 1-3 records, and
    # this is the pool the threshold narrows down to them.
    rag_top_k:     int   = 5                            # e.g. 10
    # Measured 2026-08-20 on 171 records (docs/pomiar-progu-score.md): 0.48 keeps 157 of 162 correct
    # hits and fully silences 14 of 16 distractors. The trade leans towards cutting rubbish on
    # purpose — with 47% of the corpus being singletons, "found nothing" is a normal answer, while a
    # contentless hit looks like an answer and is worse than none.
    # KNOWN COST: four correct hits drop out and THREE of them sat at rank 1, because short texts on
    # both sides score low however well they match — so this threshold systematically penalises the
    # shortest records. Do NOT raise without re-measuring: 0.50 takes four more.
    rag_score_min: float = 0.48                         # cosine similarity, range -1.0 .. 1.0

    @model_validator(mode="before")
    @classmethod
    def _drop_blank_values(cls, values: Any) -> Any:    # e.g. {"llm_model": "  "}
        """
        Description:
        Drops keys whose value is an empty or whitespace-only string, so the field falls back to
        its default. `docker compose` substitutes an EMPTY STRING for an undefined `${VAR:-}`,
        which without this would produce `Client(base_url="")` — a connection error at request
        time instead of a readable configuration error at startup.

        Example args:
            values={"qdrant_url": "", "llm_model": "gpt-4o-mini"}

        Example result:
            {"llm_model": "gpt-4o-mini"}
        """
        # Sources normally hand over a dict; anything else is passed through untouched.
        if not isinstance(values, dict):
            return values

        return {
            key: value
            for key, value in values.items()
            if not (isinstance(value, str) and value.strip() == "")
        }
