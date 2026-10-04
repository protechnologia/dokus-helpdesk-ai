import re

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.base import TOKENS_PER_UNIT, ModelPrice, price

# Odpowiedź podaje SNAPSHOT, który odpowiedział, a ten bywa z datą, o którą nie prosiliśmy:
# `claude-haiku-4-5` wraca jako `claude-haiku-4-5-20251001`. Cennik idzie po aliasie, więc sufiks
# jest obcinany przed szukaniem — wiersz na snapshot oznaczałby model bez ceny przy każdym wydaniu.
_DATE_SUFFIX = re.compile(r"-\d{8}$")

# Zapis do cache promptu z pięciominutowym czasem życia kosztuje 1,25 stawki wejścia; taki zapis
# zleca klient (`client/claude.py`). Wariant godzinny kosztuje 2,0 — nie używamy go.
CACHE_WRITE_MULTIPLIER = 1.25


# Sprawdzone z opublikowanym cennikiem 2026-10-04 (platform.claude.com/docs → Pricing).
# Nieznany identyfikator kończy się głośnym błędem w `price_of()`, a nie ceną zero: przebieg
# raportujący 0,00 USD jest gorszy niż taki, który odmawia startu, bo liczba wygląda jak odpowiedź.
# Identyfikatory bez daty — to stabilne aliasy.
# `input_usd` i `output_usd` to USD za milion tokenów; `cache_read` to ułamek stawki wejścia
# za token odczytany z cache.
PRICES: dict[str, ModelPrice] = {
    # --- obecna linia; pierwszy jest najmocniejszy ---
    "claude-fable-5-1":  price(input_usd=10.00, output_usd=50.00, cache_read=0.025),
    "claude-opus-5-5":   price(input_usd= 4.00, output_usd=20.00, cache_read=0.05),
    "claude-sonnet-5-5": price(input_usd= 2.00, output_usd=10.00, cache_read=0.10),
    "claude-haiku-4-5":  price(input_usd= 1.00, output_usd= 5.00, cache_read=0.10),

    # --- starsze, nadal dostępne ---
    "claude-opus-5":     price(input_usd= 5.00, output_usd=25.00, cache_read=0.10),
    # Cena wprowadzająca 2/10 została ceną stałą; zapowiadana podwyżka do 3/15 nie weszła.
    "claude-sonnet-5":   price(input_usd= 2.00, output_usd=10.00, cache_read=0.10),
}


def price_of(
    model: str,  # np. "claude-haiku-4-5-20251001"
) -> ModelPrice:
    """
    Description:
    Znajduje wiersz cennika modelu — po aliasie albo po snapshotcie z datą, który odsyła API.
    Nieznany identyfikator to błąd, nigdy cena zero.

    Example args:
        model="claude-haiku-4-5-20251001"

    Example result:
        ModelPrice(input_per_million=1.00, output_per_million=5.00, cache_read_multiplier=0.10)

    Raises:
        LLMConfigError: modelu nie ma w cenniku — dopisz jego opublikowane stawki wyżej
    """
    row = PRICES.get(_DATE_SUFFIX.sub("", model))

    if row is None:
        known = ", ".join(sorted(PRICES))

        raise LLMConfigError(
            f"brak cennika dla modelu {model!r}; znane modele: {known} "
            f"(dopisz stawki w app/engine_llm/pricing/claude.py)"
        )

    return row


def calculate_cost_usd(
    model:              str,      # np. "claude-haiku-4-5"
    prompt_tokens:      int,      # np. 4820 — świeże wejście, po pełnej stawce
    completion_tokens:  int,      # np. 640
    cache_write_tokens: int = 0,  # np. 1830 — po 1,25 stawki wejścia
    cache_read_tokens:  int = 0,  # np. 1830 — po ułamku stawki wejścia, zależnym od modelu
) -> float:
    """
    Description:
    Wycenia jedno wywołanie. Cztery klasy tokenów są liczone osobno, bo tak rozlicza je Anthropic:
    zlanie ich w jedną zafałszowałoby koszt każdego przebiegu z cache promptu, czyli tego, którego
    koszt kogokolwiek obchodzi.

    Example args:
        model="claude-haiku-4-5"
        prompt_tokens=4820
        completion_tokens=640
        cache_write_tokens=0
        cache_read_tokens=1830

    Example result:
        0.0082  # USD

    Raises:
        LLMConfigError: modelu nie ma w cenniku
    """
    row = price_of(model)

    billable_input = (
        prompt_tokens
        + cache_write_tokens * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens  * row.cache_read_multiplier
    )

    input_cost  = billable_input    * row.input_per_million  / TOKENS_PER_UNIT
    output_cost = completion_tokens * row.output_per_million / TOKENS_PER_UNIT

    return input_cost + output_cost
