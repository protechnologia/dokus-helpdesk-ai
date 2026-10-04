from pydantic import BaseModel, Field

# Stawki są publikowane za MILION tokenów i w tej jednostce je trzymamy: wiersz cennika da się
# wtedy porównać z opublikowaną tabelą na oko, bez liczenia.
TOKENS_PER_UNIT = 1_000_000


class ModelPrice(BaseModel):
    """
    Description:
    Opublikowana cena jednego modelu, w dolarach za milion tokenów. Jedna instancja to jeden
    wiersz cennika; tabele `PRICES` w cennikach dostawców mapują na nią identyfikator modelu.

    Dwa mnożniki mówią, jaką część stawki wejścia kosztuje token cache promptu: odczytany
    (`cache_read_multiplier`, zawsze taniej) i zapisany (`cache_write_multiplier`, drożej albo
    tak samo). Oba są w każdym wierszu, bez wartości domyślnej, bo dostawcy różnicują je między
    modelami — odczyt od 0,025 do 0,25 stawki wejścia, zapis 1,0 albo 1,25 — a wartość ukryta
    w kodzie nie dałaby się porównać z cennikiem.
    """

    input_per_million:      float = Field(gt=0, examples=[1.00])
    output_per_million:     float = Field(gt=0, examples=[5.00])
    cache_read_multiplier:  float = Field(gt=0, le=1, examples=[0.10])
    cache_write_multiplier: float = Field(ge=1, examples=[1.25])


def price(
    *,
    input:       float,  # np. 1.00 — USD za milion tokenów wejścia
    output:      float,  # np. 5.00 — USD za milion tokenów wyjścia
    cache_read:  float,  # np. 0.10 — ułamek stawki wejścia za token odczytany z cache
    cache_write: float,  # np. 1.25 — krotność stawki wejścia za token zapisany do cache
) -> ModelPrice:
    """
    Description:
    Buduje wiersz cennika z czterech nazwanych liczb. Istnieje po to, żeby tabela cen czytała się
    jak opublikowany cennik: model w wierszu, w jednej linii, każda liczba podpisana. Nazwy są
    wymagane — same liczby w nawiasie nie mówią, która jest która — i krótkie, żeby wiersz
    zmieścił się w linii.

    Example args:
        input=1.00
        output=5.00
        cache_read=0.10
        cache_write=1.25

    Example result:
        ModelPrice(input_per_million=1.00, output_per_million=5.00, cache_read_multiplier=0.10,
                   cache_write_multiplier=1.25)
    """
    row = ModelPrice(
        input_per_million      = input,
        output_per_million     = output,
        cache_read_multiplier  = cache_read,
        cache_write_multiplier = cache_write,
    )

    return row


def cost_usd(
    row:                ModelPrice,  # np. price(input=1.00, output=5.00, cache_read=0.10, …)
    prompt_tokens:      int,         # np. 4820 — świeże wejście, po pełnej stawce
    completion_tokens:  int,         # np. 640
    cache_write_tokens: int = 0,     # np. 1830 — po stawce wejścia razy mnożnik zapisu
    cache_read_tokens:  int = 0,     # np. 1830 — po stawce wejścia razy mnożnik odczytu
) -> float:
    """
    Description:
    Wycenia jedno wywołanie wierszem cennika. Cztery klasy tokenów są ROZŁĄCZNE i każda ma swoją
    stawkę: świeże wejście, zapis do cache, odczyt z cache i wyjście. Wspólne dla cenników
    wszystkich dostawców — różni je tabela, nie rachunek; klient dostawcy odpowiada za to, żeby
    klasy przyszły rozłączne.

    Example args:
        row=price(input=1.00, output=5.00, cache_read=0.10, cache_write=1.25)
        prompt_tokens=4820
        completion_tokens=640
        cache_write_tokens=0
        cache_read_tokens=1830

    Example result:
        0.0082  # USD
    """
    billable_input = (
        prompt_tokens
        + cache_write_tokens * row.cache_write_multiplier
        + cache_read_tokens  * row.cache_read_multiplier
    )

    input_cost  = billable_input    * row.input_per_million  / TOKENS_PER_UNIT
    output_cost = completion_tokens * row.output_per_million / TOKENS_PER_UNIT

    return input_cost + output_cost
