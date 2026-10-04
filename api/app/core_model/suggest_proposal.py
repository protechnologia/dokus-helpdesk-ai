from pydantic import BaseModel, ConfigDict, Field


class Proposal(BaseModel):
    """
    Description:
    Propozycja odpowiedzi dla wdrożeniowca — wynik grafów `suggest_*` (pytania, rozwiązanie,
    przekazanie sprawy).

    Do czego:
    Jeden kształt dla wszystkich wariantów, więc nowy guzik to nowy katalog grafu, a nie zmiana
    routera (CLAUDE.md -> „Warianty generacji"). Źródeł tu nie ma z założenia: lista źródeł
    powstaje z `cite()` narzędzi i leży w `sources` stanu grafu — nigdy z tego, co model
    zadeklarował (zasada 9). Wariant, którym propozycja powstała, zna wołający.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["1. Od kiedy nie przychodzą przesyłki? …"])
