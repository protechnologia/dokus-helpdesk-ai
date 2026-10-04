from pydantic import BaseModel, Field

# Stawki są publikowane za MILION tokenów i w tej jednostce je trzymamy: wiersz cennika da się
# wtedy porównać z opublikowaną tabelą na oko, bez liczenia.
TOKENS_PER_UNIT = 1_000_000


class ModelPrice(BaseModel):
    """
    Description:
    Opublikowana cena jednego modelu, w dolarach za milion tokenów. Jedna instancja to jeden
    wiersz cennika; tabele `PRICES` w cennikach dostawców mapują na nią identyfikator modelu.

    `cache_read_multiplier` mówi, jaką część stawki wejścia kosztuje token odczytany z cache
    promptu. Jest w każdym wierszu, bez wartości domyślnej, bo dostawcy różnicują go między
    modelami — od 0,025 do 0,25 stawki wejścia — a wartość ukryta w kodzie nie dałaby się
    porównać z cennikiem.
    """

    input_per_million:     float = Field(gt=0, examples=[1.00])
    output_per_million:    float = Field(gt=0, examples=[5.00])
    cache_read_multiplier: float = Field(gt=0, le=1, examples=[0.10])


def price(
    input_per_million:     float,  # np. 1.00 — USD za milion tokenów wejścia
    output_per_million:    float,  # np. 5.00 — USD za milion tokenów wyjścia
    cache_read_multiplier: float,  # np. 0.10 — ułamek stawki wejścia za odczyt z cache
) -> ModelPrice:
    """
    Description:
    Buduje wiersz cennika z trzech liczb podanych po kolei. Istnieje po to, żeby tabela cen
    czytała się jak opublikowany cennik: model w wierszu, liczby w kolumnach.

    Example args:
        input_per_million=1.00
        output_per_million=5.00
        cache_read_multiplier=0.10

    Example result:
        ModelPrice(input_per_million=1.00, output_per_million=5.00, cache_read_multiplier=0.10)
    """
    row = ModelPrice(
        input_per_million     = input_per_million,
        output_per_million    = output_per_million,
        cache_read_multiplier = cache_read_multiplier,
    )

    return row
