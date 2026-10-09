from pydantic import BaseModel, ConfigDict, Field


class ProgramOutput(BaseModel):
    """
    Description:
    Co zostało po programie, który skończył pracę: kod wyjścia i oba strumienie jako tekst.

    Co znaczy kod wyjścia, rozstrzyga klient programu, nie `run_program()`: u ripgrepa 1 to
    „nie ma trafień", a nie błąd.
    """

    model_config = ConfigDict(extra="forbid")

    returncode: int = Field(examples=[0])
    stdout:     str = Field(examples=["src/lib/Blad.php:18:    throw new Blad('…');\n"])
    stderr:     str = Field(examples=[""])
