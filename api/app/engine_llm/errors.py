class LLMError(Exception):
    """
    Description:
    Base class for every failure of the LLM layer. Callers catch this one when they only need to
    know "the model call did not produce a usable answer" — never the provider SDK's own
    exception types, which would leak the provider into the domain (CLAUDE.md -> rule 4).
    """


class LLMConfigError(LLMError):
    """
    Description:
    Raised while BUILDING a client, when configuration is missing or contradictory (unknown
    provider, no API key, no model). Deliberately a build-time failure: a misconfigured stack
    must die at startup with a readable message, not as a connection error in the middle of a
    request that already cost the user their ticket text.
    """
