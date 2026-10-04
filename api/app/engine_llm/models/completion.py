from pydantic import BaseModel, Field


class LLMCompletion(BaseModel):
    """
    Description:
    One model answer together with the accounting the logs need. The domain reads `text` only;
    the remaining fields exist so every provider reports usage in the same shape and a cost
    report can be assembled later without touching call sites.
    """

    text:              str   = Field(examples=['{"problem": "Drukarka nie drukuje"}'])
    model:             str   = Field(examples=["bielik-11b-v3"])
    prompt_tokens:     int   = Field(examples=[482])
    completion_tokens: int   = Field(examples=[96])
    latency_ms:        float = Field(examples=[1240.5])

    # Cache accounting. Providers that bill cached input separately report it here; the rest leave
    # both at zero. Kept apart from `prompt_tokens` because the rates differ by an order of
    # magnitude (a cache read costs ~0.1x a fresh token, a write ~1.25x) — folding them into one
    # number would make the cost report wrong in whichever direction the caching went.
    cache_write_tokens: int = Field(default=0, examples=[1830])
    cache_read_tokens:  int = Field(default=0, examples=[1830])

    # Priced by the client that made the call, because the price list is provider knowledge and has
    # no business leaking into the domain (rule 4). Offline providers report 0.0 — a real zero, not
    # a missing value, so a run against the fake sums to "this cost nothing" rather than to None.
    cost_usd: float = Field(default=0.0, examples=[0.0123])
