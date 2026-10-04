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

    # Rozliczenie cache promptu. Klasy są ROZŁĄCZNE u każdego dostawcy: `prompt_tokens` to samo
    # świeże wejście, a zapis do cache i odczyt z niego mają własne pola — dostawcę, który podaje
    # je wewnątrz licznika wejścia, rozdziela jego klient. Osobno, bo stawki różnią się o rząd
    # wielkości (odczyt ~0,1 stawki wejścia, zapis do 1,25): jedna liczba fałszowałaby koszt
    # w tę stronę, w którą poszło cache. Dostawca bez cache zostawia oba pola na zerze.
    cache_write_tokens: int = Field(default=0, examples=[1830])
    cache_read_tokens:  int = Field(default=0, examples=[1830])

    # Priced by the client that made the call, because the price list is provider knowledge and has
    # no business leaking into the domain (rule 4). Offline providers report 0.0 — a real zero, not
    # a missing value, so a run against the fake sums to "this cost nothing" rather than to None.
    cost_usd: float = Field(default=0.0, examples=[0.0123])
