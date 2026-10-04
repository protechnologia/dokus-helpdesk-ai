import re

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.base import ModelPrice, cost_usd, price

# Odpowiedź podaje SNAPSHOT, który odpowiedział, a ten bywa z datą, o którą nie prosiliśmy:
# `claude-haiku-4-5` wraca jako `claude-haiku-4-5-20251001`. Cennik idzie po aliasie, więc sufiks
# jest obcinany przed szukaniem — wiersz na snapshot oznaczałby model bez ceny przy każdym wydaniu.
_DATE_SUFFIX = re.compile(r"-\d{8}$")

# Sprawdzone z opublikowanym cennikiem 2026-10-04 (platform.claude.com/docs → Pricing).
# Nieznany identyfikator kończy się głośnym błędem w `price_of()`, a nie ceną zero: przebieg
# raportujący 0,00 USD jest gorszy niż taki, który odmawia startu, bo liczba wygląda jak odpowiedź.
# Identyfikatory bez daty — to stabilne aliasy.
# `input` i `output` to USD za milion tokenów; `cache_read` i `cache_write` to krotności stawki
# wejścia za token odczytany z cache promptu i zapisany do niego. Zapis 1,25 dotyczy cache
# z pięciominutowym czasem życia — taki zleca klient (`client/claude.py`); wariant godzinny
# kosztuje 2,0 i go nie używamy.
PRICES: dict[str, ModelPrice] = {
    # --- obecna linia; pierwszy jest najmocniejszy ---
    "claude-fable-5-1":  price(input=10.00, output=50.00, cache_read=0.025, cache_write=1.25),
    "claude-opus-5-5":   price(input= 4.00, output=20.00, cache_read=0.050, cache_write=1.25),
    "claude-sonnet-5-5": price(input= 2.00, output=10.00, cache_read=0.100, cache_write=1.25),
    "claude-haiku-4-5":  price(input= 1.00, output= 5.00, cache_read=0.100, cache_write=1.25),

    # --- starsze, nadal dostępne ---
    "claude-opus-5":     price(input= 5.00, output=25.00, cache_read=0.100, cache_write=1.25),
    # Cena wprowadzająca 2/10 została ceną stałą; zapowiadana podwyżka do 3/15 nie weszła.
    "claude-sonnet-5":   price(input= 2.00, output=10.00, cache_read=0.100, cache_write=1.25),
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
        ModelPrice(input_per_million=1.00, output_per_million=5.00, cache_read_multiplier=0.10,
                   cache_write_multiplier=1.25)

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
    cache_write_tokens: int = 0,  # np. 1830 — po krotności stawki wejścia z wiersza modelu
    cache_read_tokens:  int = 0,  # np. 1830 — po ułamku stawki wejścia z wiersza modelu
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
    cost = cost_usd(
        row                = price_of(model),
        prompt_tokens      = prompt_tokens,
        completion_tokens  = completion_tokens,
        cache_write_tokens = cache_write_tokens,
        cache_read_tokens  = cache_read_tokens,
    )

    return cost
