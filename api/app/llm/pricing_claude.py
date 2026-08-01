import re

from pydantic import BaseModel, Field

from app.llm.errors import LLMConfigError

# Prices are published per MILLION tokens; we keep them in that unit rather than pre-dividing, so a
# row can be checked against the price list by eye without decoding scientific notation.
TOKENS_PER_UNIT = 1_000_000

# A response reports the SNAPSHOT that answered, which may carry a release date the request did not:
# asking for `claude-haiku-4-5` comes back as `claude-haiku-4-5-20251001`, while `claude-sonnet-5`
# comes back unchanged. Pricing follows the alias, so the suffix is trimmed before lookup — keeping
# a row per snapshot would mean an unpriced model, and a failed run, on every future release.
_DATE_SUFFIX = re.compile(r"-\d{8}$")

# Multipliers Anthropic applies to the INPUT rate for prompt caching. Writing a cache entry costs a
# premium, reading one is nearly free — which is the whole reason `LLMCompletion` keeps the two
# token counts apart instead of merging them into `prompt_tokens`.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER  = 0.10


class ModelPrice(BaseModel):
    """
    Description:
    The published price of one model, in USD per million tokens. One instance is one row of the
    price list; `PRICES` below maps a model id to it.
    """

    input_per_million:  float = Field(examples=[1.00])
    output_per_million: float = Field(examples=[5.00])


# Verified against the published price list on 2026-08-01. This table is the reason a stale build
# cannot silently misreport cost: an unknown model id fails loudly in `price_of()` instead of being
# priced at zero, so adding a model is a deliberate edit here rather than an accident at runtime.
# Ids carry no date suffix on purpose — these are the stable aliases.
PRICES: dict[str, ModelPrice] = {
    "claude-haiku-4-5":  ModelPrice(input_per_million = 1.00, output_per_million =  5.00),
    "claude-sonnet-5":   ModelPrice(input_per_million = 3.00, output_per_million = 15.00),
    "claude-opus-5":     ModelPrice(input_per_million = 5.00, output_per_million = 25.00),
}


def price_of(model: str) -> ModelPrice:   # e.g. "claude-haiku-4-5-20251001"
    """
    Description:
    Looks up the price row of one model, accepting either the alias or the dated snapshot the API
    reports back. Fails loudly on an unknown id rather than defaulting to zero: a run whose cost
    silently reports as $0.00 is worse than one that refuses to start, because the number looks
    like an answer.

    Example args:
        model="claude-haiku-4-5-20251001"

    Example result:
        ModelPrice(input_per_million=1.00, output_per_million=5.00)

    Raises:
        LLMConfigError: the model is not in the price table — add its published rates above
    """
    price = PRICES.get(_DATE_SUFFIX.sub("", model))

    if price is None:
        known = ", ".join(sorted(PRICES))

        raise LLMConfigError(
            f"brak cennika dla modelu {model!r}; znane modele: {known} "
            f"(dopisz stawki w app/llm/pricing_claude.py)"
        )

    return price


def calculate_cost_usd(
    model:              str,      # e.g. "claude-haiku-4-5"
    prompt_tokens:      int,      # e.g. 4820 — fresh input, billed at the full input rate
    completion_tokens:  int,      # e.g. 640
    cache_write_tokens: int = 0,  # e.g. 1830 — billed at 1.25x the input rate
    cache_read_tokens:  int = 0,  # e.g. 1830 — billed at 0.10x the input rate
) -> float:
    """
    Description:
    Prices one call. The four token classes are billed separately because Anthropic bills them
    separately — collapsing them would misreport any run that used prompt caching, which is
    exactly the run whose cost anyone cares about.

    Example args:
        model="claude-haiku-4-5"
        prompt_tokens=4820
        completion_tokens=640
        cache_write_tokens=0
        cache_read_tokens=1830

    Example result:
        0.0100  # USD

    Raises:
        LLMConfigError: the model is not in the price table
    """
    price = price_of(model)

    billable_input = (
        prompt_tokens
        + cache_write_tokens * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens  * CACHE_READ_MULTIPLIER
    )

    input_cost  = billable_input    * price.input_per_million  / TOKENS_PER_UNIT
    output_cost = completion_tokens * price.output_per_million / TOKENS_PER_UNIT

    return input_cost + output_cost
