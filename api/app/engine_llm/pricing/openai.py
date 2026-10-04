import re

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.base import TOKENS_PER_UNIT, ModelPrice, price

# Odpowiedź podaje SNAPSHOT, który odpowiedział, z datą wydania, o którą nie prosiliśmy:
# `gpt-5.4-mini` wraca jako `gpt-5.4-mini-2026-03-17` (sprawdzone na żywym API 2026-08-02). Cennik
# idzie po aliasie, więc sufiks jest obcinany przed szukaniem.
_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# Sprawdzone z opublikowanym cennikiem 2026-10-04 (developers.openai.com → API → Pricing, tabela
# „Standard", kontekst krótki). Nieznany identyfikator kończy się głośnym błędem w `price_of()`,
# a nie ceną zero: przebieg raportujący 0,00 USD jest gorszy niż taki, który odmawia startu.
#
# Czego ta tabela NIE obejmuje:
# - stawek „long context" (powyżej 272 tys. tokenów wejścia) — nasze prompty są o rzędy krótsze;
# - stawki ZAPISU do cache, którą cennik podaje dla rodzin gpt-6 i gpt-5.6 (1,25 stawki wejścia).
#   Klient odczytuje dziś tylko licznik odczytów z cache, więc zapis jest liczony jak zwykłe
#   wejście — koszt pierwszej tury z nowym początkiem promptu jest zaniżony o 25% tej części.
#
# `input_usd` i `output_usd` to USD za milion tokenów; `cache_read` to ułamek stawki wejścia
# za token odczytany z cache.
PRICES: dict[str, ModelPrice] = {
    # --- rodzina gpt-6; pierwszy jest najmocniejszy w cenniku ---
    "gpt-6-astra":   price(input_usd=10.00, output_usd=50.00, cache_read=0.10),
    "gpt-6.1-sol":   price(input_usd= 2.00, output_usd=10.00, cache_read=0.05),
    "gpt-6-sol":     price(input_usd= 2.00, output_usd=10.00, cache_read=0.10),
    "gpt-6-luna":    price(input_usd= 0.10, output_usd= 0.50, cache_read=0.10),

    # --- rodzina gpt-5.6 ---
    "gpt-5.6-sol":   price(input_usd= 4.00, output_usd=20.00, cache_read=0.10),
    "gpt-5.6-terra": price(input_usd= 2.00, output_usd=12.00, cache_read=0.10),
    "gpt-5.6-luna":  price(input_usd= 0.20, output_usd= 1.20, cache_read=0.10),

    # --- gpt-5.5 i gpt-5.4 ---
    "gpt-5.5":       price(input_usd= 5.00, output_usd=30.00, cache_read=0.10),
    "gpt-5.4":       price(input_usd= 2.50, output_usd=15.00, cache_read=0.10),
    "gpt-5.4-mini":  price(input_usd= 0.75, output_usd= 4.50, cache_read=0.10),
    "gpt-5.4-nano":  price(input_usd= 0.20, output_usd= 1.25, cache_read=0.10),

    # --- starsze, użyte w porównaniu modeli parsowania ---
    "gpt-4.1":       price(input_usd= 2.00, output_usd= 8.00, cache_read=0.25),
    "gpt-4.1-mini":  price(input_usd= 0.40, output_usd= 1.60, cache_read=0.25),
    "o4-mini":       price(input_usd= 1.10, output_usd= 4.40, cache_read=0.25),
}


def price_of(
    model: str,  # np. "gpt-5.4-mini-2026-03-17"
) -> ModelPrice:
    """
    Description:
    Znajduje wiersz cennika modelu — po aliasie albo po snapshotcie z datą, który odsyła API.
    Nieznany identyfikator to błąd, nigdy cena zero.

    Example args:
        model="gpt-5.4-mini-2026-03-17"

    Example result:
        ModelPrice(input_per_million=0.75, output_per_million=4.50, cache_read_multiplier=0.10)

    Raises:
        LLMConfigError: modelu nie ma w cenniku — dopisz jego opublikowane stawki wyżej
    """
    row = PRICES.get(_DATE_SUFFIX.sub("", model))

    if row is None:
        known = ", ".join(sorted(PRICES))

        raise LLMConfigError(
            f"brak cennika dla modelu {model!r}; znane modele: {known} "
            f"(dopisz stawki w app/engine_llm/pricing/openai.py)"
        )

    return row


def calculate_cost_usd(
    model:              str,      # np. "gpt-5.4-mini"
    prompt_tokens:      int,      # np. 4820 — całe wejście, razem z częścią odczytaną z cache
    completion_tokens:  int,      # np. 640 — w modelach rozumujących także tokeny rozumowania
    cache_read_tokens:  int = 0,  # np. 1830 — po ułamku stawki wejścia, zależnym od modelu
) -> float:
    """
    Description:
    Wycenia jedno wywołanie. Wejście odczytane z cache jest liczone osobno, bo jego stawka jest
    kilkukrotnie niższa. Klasy zapisu do cache tu nie ma — klient jej nie odczytuje.

    W modelach rozumujących (o4-mini) `completion_tokens` obejmuje tokeny, których wołający nie
    widzi: za myślenie się płaci, po stawce wyjścia.

    Example args:
        model="gpt-5.4-mini"
        prompt_tokens=4820
        completion_tokens=640
        cache_read_tokens=1830

    Example result:
        0.00526  # USD

    Raises:
        LLMConfigError: modelu nie ma w cenniku
    """
    row = price_of(model)

    # W tym API tokeny z cache siedzą WEWNĄTRZ `prompt_tokens`, więc dostają zniżkę, a nie są
    # doliczane: policzenie ich drugi raz zawyżyłoby koszt początku promptu.
    fresh_input = max(prompt_tokens - cache_read_tokens, 0)

    billable_input = fresh_input + cache_read_tokens * row.cache_read_multiplier

    input_cost  = billable_input    * row.input_per_million  / TOKENS_PER_UNIT
    output_cost = completion_tokens * row.output_per_million / TOKENS_PER_UNIT

    return input_cost + output_cost
