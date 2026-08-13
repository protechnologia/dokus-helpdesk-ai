class RetrievalError(Exception):
    """
    Description:
    Base class for every failure of the retrieval layer. Callers catch this one when all they
    need to know is "the index did not answer" — never `httpx` exception types, which would leak
    the transport into the domain (CLAUDE.md -> rule 4).

    Deliberately separate from `EmbeddingError`: the two cross DIFFERENT process boundaries and
    fail for different reasons. An unreachable embedder means no vectors were computed; an
    unreachable Qdrant means vectors exist but have nowhere to go. During an indexing run those
    demand different reactions, and one shared class would erase the difference.
    """


class RetrievalConfigError(RetrievalError):
    """
    Description:
    Raised while BUILDING a client, or when the existing collection contradicts the configuration
    it is supposed to match (a different vector size, a missing named vector).

    Build-time failure on purpose. Both cases are unfixable by waiting, so they must not reach the
    503 handler that means "retry later" (CLAUDE.md -> "Logi i obserwowalność"). The dimension
    check matters most: without it a mismatch surfaces as points rejected by Qdrant an hour into
    an indexing run — after the expensive LLM parsing has already been paid for.
    """
