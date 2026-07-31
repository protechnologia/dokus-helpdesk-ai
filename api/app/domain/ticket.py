from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.rules.resolution import get_resolution_classes

# Every text field may say "there is nothing here" instead of being left out. A required field
# forces the model to invent a value (CLAUDE.md -> "Jak projektować schemat odpowiedzi"), and an
# invented cause is worse than a missing one — it looks like knowledge.
NO_VALUE       = "brak"
NOT_APPLICABLE = "nie dotyczy"

# Fields that feed the embedding vector. Kept as a constant because indexing (stage 4) and the
# runtime query (stage 5) MUST build the text the same way — two call sites drifting apart would
# silently produce vectors that cannot be compared.
EMBEDDED_FIELDS = ("problem", "symptoms")


class ParsedTicket(BaseModel):
    """
    Description:
    The contract of a parsed ticket — the durable artifact of the whole project. One instance is
    one JSON file in `data/parsed/`, and this class is what decides whether that file is valid.

    Do czego:
    Raw tickets never reach the index. An LLM turns each conversation into this structure, and
    only this structure feeds embeddings and the Qdrant payload (CLAUDE.md -> "Cel"). The LLM run
    is expensive and one-off, so the artifact is permanent while embeddings and collections are
    disposable — a re-index must never call the model again (rule 7).

    Flow:
        1. An adapter in `ingest/` fills the fields taken straight from the source: `ticket_id`,
           `date`.
        2. The parsing prompt fills the rest from the whole conversation thread — including
           `cause`, which no source column holds.
        3. `resolution_vocabulary_version` records which vocabulary produced `resolution`, so a
           later edit of that vocabulary does not silently invalidate this file.
        4. Indexing embeds `problem` + `symptoms`; everything else travels in the payload.

    Scope assumption: one product instance serves ONE helpdesked product, which is why there is
    no `system` field — the application name is instance configuration, not per-record data.
    """

    # Unknown keys are an ERROR, not something to drop quietly. Models do break a closed field
    # list and invent their own keys, and that content is often valuable (CLAUDE.md -> "Jak
    # projektować schemat odpowiedzi"). Pydantic's default would discard it without a trace —
    # unacceptable when the LLM run producing it is expensive and one-off (rule 7). Failing loudly
    # means the prompt or the schema gets fixed BEFORE the corpus-wide run, not after.
    model_config = ConfigDict(extra="forbid")

    # --- identity: from the adapter, never from the model ---
    ticket_id: str  = Field(examples=["33644"])
    date:      Date = Field(examples=["2026-03-14"])

    # --- what the ticket is about ---
    # Free text, not a vocabulary: the value set has a long thin tail (a handful of integrations
    # dominate, the rest appear once or twice), so a closed enum would force a deploy per new
    # customer integration. Cost accepted knowingly: spelling variants of the same service are
    # likely across a full corpus run, so this field is DESCRIPTIVE and unfit as a Qdrant filter
    # without normalisation (CLAUDE.md -> "Domena").
    component: str = Field(examples=["główna aplikacja", "ePUAP", "e-Doręczenia"])

    # --- the vector side: the only two fields that become the embedding ---
    problem:  str = Field(examples=["Wysyłka przez ePUAP kończy się błędem komunikacji"])
    symptoms: str = Field(examples=["Po kliknięciu Wyślij pojawia się komunikat o braku sieci"])

    # --- the payload side: what the answer is built from ---
    error_codes: list[str] = Field(default_factory=list, examples=[["ERR-4210", "SQLSTATE 23000"]])
    cause:       str       = Field(examples=["Certyfikat bez uprawnienia AddDocumentToSign"])
    # Caveats live INSIDE this text rather than in a field of their own. They are not decoration:
    # "the setting is global", "works from now on, there is no route for the backlog" — dropping
    # such a sentence turns the answer into its opposite, so both prompts must carry it over.
    solution:    str       = Field(examples=["Wygenerowano certyfikat z właściwym uprawnieniem."])

    # --- classification and diagnostics ---
    resolution: str = Field(examples=["naprawione"])
    # The vocabulary is customer data and may change; the artifact must remember what it meant.
    resolution_vocabulary_version: int = Field(examples=[1])
    # Empty in most records and that is the normal state, not a defect: only a minority of
    # tickets contain a consultant's diagnostic question at all.
    questions_summary: str = Field(default=NO_VALUE, examples=["pytano o wersję przeglądarki"])

    @field_validator("component", "problem", "symptoms", "cause", "solution", "questions_summary")
    @classmethod
    def _reject_blank(cls, value: str) -> str:          # e.g. "  "
        """
        Description:
        Rejects empty and whitespace-only text. The schema already offers an explicit way out
        (`brak` / `nie dotyczy`); a blank string is a different thing — a field the model skipped,
        which would enter the corpus looking like an answered one.

        Example args:
            value="   "

        Example result:
            ValueError — the caller must write `brak` instead

        Raises:
            ValueError: the value is empty or whitespace only
        """
        if not value.strip():
            raise ValueError(f"pole nie może być puste — użyj {NO_VALUE!r} albo {NOT_APPLICABLE!r}")

        return value.strip()

    @model_validator(mode="after")
    def _check_resolution_against_vocabulary(self) -> "ParsedTicket":
        """
        Description:
        Verifies that `resolution` is a value the recorded vocabulary version actually declares.
        Checked against the version stored IN the record, not against whatever is configured now —
        otherwise editing the vocabulary would retroactively invalidate correct old artifacts,
        which is exactly what versioning exists to prevent (rule 7).

        Example args:
            (self, already populated)

        Example result:
            The same instance, unchanged

        Raises:
            ValueError: `resolution` is outside the vocabulary, or the record was produced with a
                vocabulary version this build no longer ships
        """
        vocabulary = get_resolution_classes()

        # A record from a newer (or older) vocabulary cannot be judged by the one we ship. Say so
        # plainly instead of reporting a misleading "unknown value".
        if self.resolution_vocabulary_version != vocabulary.version:
            raise ValueError(
                f"rekord powstał ze słownika w wersji {self.resolution_vocabulary_version}, "
                f"a ta instalacja ma wersję {vocabulary.version} — re-parsing albo starszy słownik"
            )

        allowed = vocabulary.names()

        if self.resolution not in allowed:
            raise ValueError(
                f"resolution={self.resolution!r} spoza słownika; dozwolone: {', '.join(allowed)}"
            )

        return self

    def embedding_text(self) -> str:
        """
        Description:
        Builds the text that becomes this record's vector. Lives on the model so indexing and the
        runtime query cannot drift apart — two call sites assembling it by hand would eventually
        produce vectors nobody can compare, and nothing would fail loudly.

        `solution` is deliberately absent: we search by similarity of the PROBLEM, and a vector
        polluted with the answer mixes both signals (CLAUDE.md -> "Domena").

        Example args:
            (none)

        Example result:
            "Wysyłka przez ePUAP kończy się błędem komunikacji\\nPo kliknięciu Wyślij…"
        """
        return "\n".join(getattr(self, field) for field in EMBEDDED_FIELDS)
