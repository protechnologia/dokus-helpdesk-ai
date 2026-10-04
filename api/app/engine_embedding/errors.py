class EmbeddingError(Exception):
    """
    Description:
    Base class for every failure of the embedding layer. Callers catch this one when they only
    need to know "no vectors came back" — never `httpx` exception types, which would leak the
    transport into the domain (CLAUDE.md -> rule 4). The `embedder` service has its own
    `EncoderError` on the other side of the wire; this is its counterpart in `api`, and the two
    are deliberately separate classes because the services share no code, only the HTTP contract.
    """


class EmbeddingConfigError(EmbeddingError):
    """
    Description:
    Raised while BUILDING a client, when configuration is missing or contradictory (no base URL).
    Deliberately a build-time failure: a misconfigured stack must die at startup with a readable
    message, not as a connection error in the middle of an indexing run that already paid for
    LLM parsing.
    """
