from pydantic import BaseModel, Field


class Embeddings(BaseModel):
    """
    Description:
    Wektory jednej partii tekstów razem z nazwą modelu, który je policzył — tak, jak oddała je
    usługa `embedder`, po wektorze na tekst, w kolejności tekstów.

    Do czego:
    Model TRANSPORTU pakietu (CLAUDE.md -> „Warstwy kodu"). Nazwa modelu jedzie razem
    z wektorami, bo wektory dwóch modeli nie są porównywalne, nawet przy tym samym wymiarze:
    zapis i wyszukiwanie w Qdrancie sprawdzają ją wobec modelu, którym policzono punkty kolekcji.
    O tym, który model działa — także czy to atrapa — decyduje konfiguracja usługi, nie `api`.
    """

    model:   str               = Field(examples=["OPI-PIB/PolDense-150M"])
    vectors: list[list[float]] = Field(examples=[[[0.0123, -0.0456]]])
