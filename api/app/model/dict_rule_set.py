from pydantic import BaseModel, Field


class RuleSet(BaseModel):
    """
    Description:
    Zestaw reguł klienta dla jednego grafu (bramka zamknięcia, bramka wysyłki, „Popraw") i wersja,
    w której go wczytano.

    Do czego:
    Reguły to DANE klienta o jego procesie, nie nasza logika: wchodzą do oddzielonej sekcji promptu
    grafu, a szkielet promptu zostaje w repo (CLAUDE.md -> „Reguły jako dane"). Wersja wraca
    w odpowiedzi bramki, bo bez niej „dlaczego wczoraj przeszło, a dziś nie" jest nie do
    odtworzenia. Pusta lista to błąd — bramka bez reguł nie ma czego sprawdzać.
    """

    version:     int       = Field(examples=[1])
    description: str       = Field(default="", examples=["DANE KLIENTA, nie nasz kod…"])
    rules:       list[str] = Field(min_length=1, examples=[["Z treści wynika, co było problemem."]])
