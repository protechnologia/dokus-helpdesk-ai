import re

from app.llm.errors import LLMConfigError
from app.llm.pricing_claude import ModelPrice

# Prices are published per MILLION tokens; kept in that unit so a row can be checked against the
# published list by eye. Shared with the Claude table rather than redefined — the unit is a property
# of how vendors publish prices, not of one vendor.
TOKENS_PER_UNIT = 1_000_000

# A response reports the SNAPSHOT that answered, carrying a release date the request did not: asking
# for `gpt-5.4-mini` comes back as `gpt-5.4-mini-2026-03-17`. Verified against the live API on
# 2026-08-02. Pricing follows the alias, so the suffix is trimmed before lookup.
_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# Multiplier OpenAI applies to the INPUT rate for a cached prompt prefix. There is no write premium
# here — unlike Anthropic, caching is automatic and only the READ side is discounted, so a single
# multiplier covers it (verified against the published price list on 2026-08-02).
CACHE_READ_MULTIPLIER = 0.10


# Verified against the published price list on 2026-08-02. An unknown id fails loudly in
# `price_of()` rather than being priced at zero: a run reporting $0.00 is worse than one refusing
# to start, because the number looks like an answer.
PRICES: dict[str, ModelPrice] = {
    "gpt-5.4":       ModelPrice(input_per_million = 2.50, output_per_million = 15.00),
    "gpt-5.4-mini":  ModelPrice(input_per_million = 0.75, output_per_million =  4.50),
    "gpt-4.1":       ModelPrice(input_per_million = 2.00, output_per_million =  8.00),
    "gpt-4.1-mini":  ModelPrice(input_per_million = 0.40, output_per_million =  1.60),
    "o4-mini":       ModelPrice(input_per_million = 1.10, output_per_million =  4.40),
}


def price_of(model: str) -> ModelPrice:   # e.g. "gpt-5.4-mini-2026-03-17"
    """
    Description:
    Looks up the price row of one model, accepting either the alias or the dated snapshot the API
    reports back. Fails loudly on an unknown id rather than defaulting to zero.

    Example args:
        model="gpt-5.4-mini-2026-03-17"

    Example result:
        ModelPrice(input_per_million=0.75, output_per_million=4.50)

    Raises:
        LLMConfigError: the model is not in the price table — add its published rates above
    """
    price = PRICES.get(_DATE_SUFFIX.sub("", model))

    if price is None:
        known = ", ".join(sorted(PRICES))

        raise LLMConfigError(
            f"brak cennika dla modelu {model!r}; znane modele: {known} "
            f"(dopisz stawki w app/llm/pricing_openai.py)"
        )

    return price


def calculate_cost_usd(
    model:              str,      # e.g. "gpt-5.4-mini"
    prompt_tokens:      int,      # e.g. 4820 — fresh input, billed at the full input rate
    completion_tokens:  int,      # e.g. 640 — includes reasoning tokens on reasoning models
    cache_read_tokens:  int = 0,  # e.g. 1830 — billed at 0.10x the input rate
) -> float:
    """
    Description:
    Prices one call. Cached input is billed separately because the rate differs by an order of
    magnitude; there is no cache-write class on this provider, so the signature carries one cache
    argument rather than the two the Claude table needs.

    On reasoning models (o4-mini) `completion_tokens` includes tokens the caller never sees — the
    model is billed for thinking. Pricing them at the output rate is correct and deliberate: a
    one-word answer from o4-mini cost 83 output tokens in the probe on 2026-08-02.

    Example args:
        model="gpt-5.4-mini"
        prompt_tokens=4820
        completion_tokens=640
        cache_read_tokens=1830

    Example result:
        0.0064  # USD

    Raises:
        LLMConfigError: the model is not in the price table
    """
    price = price_of(model)

    # Cached tokens arrive INSIDE `prompt_tokens` in this API, so they are discounted rather than
    # added: billing them again on top would double-charge the cached prefix.
    fresh_input = max(prompt_tokens - cache_read_tokens, 0)

    billable_input = fresh_input + cache_read_tokens * CACHE_READ_MULTIPLIER

    input_cost  = billable_input    * price.input_per_million  / TOKENS_PER_UNIT
    output_cost = completion_tokens * price.output_per_million / TOKENS_PER_UNIT

    return input_cost + output_cost
