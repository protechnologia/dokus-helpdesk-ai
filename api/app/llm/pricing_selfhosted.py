from app.llm.pricing_claude import ModelPrice

# A model running on our own hardware bills no tokens, whoever serves it — Ollama today, vLLM or
# Bielik on a rented GPU later. The rate is a genuine, measured zero, not the missing price row the
# hosted tables fail loudly on.
#
# Named after the way the model is HOSTED rather than after the tool serving it: `client_ollama.py`
# is one consumer of this table, and the next runner will be another. Keeping it out of
# `pricing_openai.py` keeps the distinction visible — that table is a copy of a published price
# list and gets re-verified against it, this one states a property of where the model runs.
FREE = ModelPrice(input_per_million = 0.0, output_per_million = 0.0)


def price_of(model: str) -> ModelPrice:   # e.g. "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    """
    Description:
    Prices any self-hosted model at zero. Accepts every id on purpose: a local tag names a
    publisher, a parameter count and a quantisation, and pulling a new one costs nothing — a
    whitelist would block a run for no reason, while the risk it guards against on hosted providers
    (silently reporting a real bill as $0.00) does not exist here.

    Example args:
        model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"

    Example result:
        ModelPrice(input_per_million=0.0, output_per_million=0.0)
    """
    return FREE


def calculate_cost_usd(
    model:             str,      # e.g. "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    prompt_tokens:     int,      # e.g. 4820
    completion_tokens: int,      # e.g. 640
    cache_read_tokens: int = 0,  # e.g. 0 — self-hosted runners report no cache counters
) -> float:
    """
    Description:
    Reports the cost of one self-hosted call: always zero. The signature mirrors the hosted tables
    so a client can call either without knowing which one it holds.

    The real cost of a local run is TIME, not money — a 4.5B model on CPU answers in minutes rather
    than seconds. The money column is uninformative here by construction; the elapsed time the CLI
    prints beside it is the one that matters.

    Example args:
        model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
        prompt_tokens=4820
        completion_tokens=640
        cache_read_tokens=0

    Example result:
        0.0  # USD — our own hardware bills no tokens
    """
    return 0.0
