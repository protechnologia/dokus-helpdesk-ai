class EncoderError(Exception):
    """
    Description:
    Base class for every failure of the encoding layer. The router catches this one when it only
    needs to know "no vectors were produced" — never a model library's own exception types, which
    would tie the HTTP layer to whichever backend happens to be configured.
    """


class EncoderConfigError(EncoderError):
    """
    Description:
    Raised while BUILDING an encoder, when configuration is missing or contradictory (unknown
    backend, no model name, a model whose dimension contradicts the configured one). Deliberately
    a build-time failure: a misconfigured embedder must die at startup, not turn into vectors of
    the wrong width that Qdrant rejects an hour into an indexing run.
    """
