import re

from app.engine_llm.errors import LLMConfigError
from app.engine_llm.pricing.base import ModelPrice, cost_usd, price

# Odpowiedź podaje SNAPSHOT, który odpowiedział, z datą wydania, o którą nie prosiliśmy:
# `gpt-5.4-mini` wraca jako `gpt-5.4-mini-2026-03-17` (sprawdzone na żywym API 2026-08-02). Cennik
# idzie po aliasie, więc sufiks jest obcinany przed szukaniem.
_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# Sprawdzone z opublikowanym cennikiem 2026-10-04 (developers.openai.com → API → Pricing, tabela
# „Standard", kontekst krótki). Nieznany identyfikator kończy się głośnym błędem w `price_of()`,
# a nie ceną zero: przebieg raportujący 0,00 USD jest gorszy niż taki, który odmawia startu.
#
# Czego ta tabela NIE obejmuje: stawek „long context" (powyżej 272 tys. tokenów wejścia) — nasze
# prompty są o rzędy krótsze.
#
# `input` i `output` to USD za milion tokenów; `cache_read` i `cache_write` to krotności stawki
# wejścia za token odczytany z cache promptu i zapisany do niego. Zapis kosztuje 1,25 stawki
# wejścia w rodzinach gpt-6 i gpt-5.6; starsze modele nie mają osobnej stawki zapisu, więc
# dostają 1,00 — zapis jest tam zwykłym wejściem.
PRICES: dict[str, ModelPrice] = {
    # --- rodzina gpt-6; pierwszy jest najmocniejszy w cenniku ---
    "gpt-6-astra":   price(input=10.00, output=50.00, cache_read=0.10, cache_write=1.25),
    "gpt-6.1-sol":   price(input= 2.00, output=10.00, cache_read=0.05, cache_write=1.25),
    "gpt-6-sol":     price(input= 2.00, output=10.00, cache_read=0.10, cache_write=1.25),
    "gpt-6-luna":    price(input= 0.10, output= 0.50, cache_read=0.10, cache_write=1.25),

    # --- rodzina gpt-5.6 ---
    "gpt-5.6-sol":   price(input= 4.00, output=20.00, cache_read=0.10, cache_write=1.25),
    "gpt-5.6-terra": price(input= 2.00, output=12.00, cache_read=0.10, cache_write=1.25),
    "gpt-5.6-luna":  price(input= 0.20, output= 1.20, cache_read=0.10, cache_write=1.25),

    # --- gpt-5.5 i gpt-5.4 ---
    "gpt-5.5":       price(input= 5.00, output=30.00, cache_read=0.10, cache_write=1.00),
    "gpt-5.4":       price(input= 2.50, output=15.00, cache_read=0.10, cache_write=1.00),
    "gpt-5.4-mini":  price(input= 0.75, output= 4.50, cache_read=0.10, cache_write=1.00),
    "gpt-5.4-nano":  price(input= 0.20, output= 1.25, cache_read=0.10, cache_write=1.00),

    # --- starsze, użyte w porównaniu modeli parsowania ---
    "gpt-4.1":       price(input= 2.00, output= 8.00, cache_read=0.25, cache_write=1.00),
    "gpt-4.1-mini":  price(input= 0.40, output= 1.60, cache_read=0.25, cache_write=1.00),
    "o4-mini":       price(input= 1.10, output= 4.40, cache_read=0.25, cache_write=1.00),
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
        ModelPrice(input_per_million=0.75, output_per_million=4.50, cache_read_multiplier=0.10,
                   cache_write_multiplier=1.00)

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
    prompt_tokens:      int,      # np. 4820 — świeże wejście, po pełnej stawce
    completion_tokens:  int,      # np. 640 — w modelach rozumujących także tokeny rozumowania
    cache_write_tokens: int = 0,  # np. 1830 — po krotności stawki wejścia z wiersza modelu
    cache_read_tokens:  int = 0,  # np. 1830 — po ułamku stawki wejścia z wiersza modelu
) -> float:
    """
    Description:
    Wycenia jedno wywołanie. Wejście ma trzy rozłączne klasy — świeże, zapisane do cache
    i odczytane z cache — każdą po swojej stawce; zapis nie jest dopłatą do wejścia, tylko
    inną stawką za te same tokeny. API podaje obie klasy cache WEWNĄTRZ `prompt_tokens`,
    a rozdziela je klient (`client/openai.py`), więc tutaj przychodzą już osobno.

    W modelach rozumujących `completion_tokens` obejmuje tokeny, których wołający nie widzi:
    za myślenie się płaci, po stawce wyjścia.

    Example args:
        model="gpt-5.4-mini"
        prompt_tokens=2990
        completion_tokens=640
        cache_write_tokens=0
        cache_read_tokens=1830

    Example result:
        0.00526  # USD

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
