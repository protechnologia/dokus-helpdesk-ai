from pydantic import BaseModel, ConfigDict, Field


class FoundLine(BaseModel):
    """
    Description:
    Jedna linia pliku znaleziona przez ripgrepa: w którym pliku stoi, pod którym numerem i co
    w niej jest.

    Ścieżka jest względna wobec katalogu, w którym szukano, a numer liczony od 1. Treść jest
    cała, z wcięciem i bez znaku końca linii: co z niej pokazać dalej, rozstrzyga wołający.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, examples=["src/lib/Urzad/Numeracja/GeneratorNumeru.php"])
    line: int = Field(ge=1, examples=[18])
    text: str = Field(examples=["            throw new BrakSekwencjiException('Brak…');"])
