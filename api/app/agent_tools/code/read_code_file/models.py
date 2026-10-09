from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Najwyżej tyle linii oddaje jeden odczyt; dłuższy plik czyta się kolejnymi wywołaniami. W paczce
# kodu Dokusa mieści się w tym w całości 92% plików (przy 150 liniach 84%, przy 400 — 95%).
MAX_LINES_PER_READ = 300


class ReadCodeFileQuery(BaseModel):
    """
    Description:
    O co agent prosi `read_code_file`: jeden plik z kodu aplikacji, w całości albo od linii do
    linii włącznie. Numery linii nazywają się tak samo jak w `quote_code`, więc model cytuje
    przeczytany fragment tymi samymi liczbami, bez przeliczania.

    Oba numery są opcjonalne: bez nich odczyt idzie od pierwszej linii do końca pliku. Zakres
    dłuższy niż `MAX_LINES_PER_READ` nie jest błędem — narzędzie oddaje jego początek i mówi
    w wyniku, że limit urwał odczyt.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    path:      str        = Field(min_length=1, examples=["src/lib/Urzad/Numeracja/Generator.php"])
    # Numery linii liczone od 1, obie granice należą do zakresu.
    from_line: int        = Field(default=1, ge=1, examples=[14])
    # Brak znaczy „do końca pliku".
    to_line:   int | None = Field(default=None, ge=1, examples=[60])

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        """
        Description:
        Odrzuca zakres, który kończy się przed swoim początkiem. Błąd wraca do modelu jako błędne
        argumenty, z obiema liczbami.

        Example args:
            (brak)

        Example result:
            ReadCodeFileQuery(path="src/lib/…/Generator.php", from_line=14, to_line=60)

        Raises:
            ValueError: `to_line` mniejsze niż `from_line`
        """
        if self.to_line is not None and self.to_line < self.from_line:
            raise ValueError(
                f"to_line ({self.to_line}) jest mniejsze niż from_line ({self.from_line})"
            )

        return self


class CodeFileInfo(BaseModel):
    """
    Description:
    Co `read_code_file` mówi o całym pliku, niezależnie od tego, który zakres oddało: ile plik ma
    linii. Po tej liczbie model widzi, ile zostało do przeczytania i gdzie plik się kończy.
    """

    model_config = ConfigDict(extra="forbid")

    total_lines: int = Field(ge=1, examples=[441])


class RequestedLines(BaseModel):
    """
    Description:
    Zakres linii, o który agent prosił `read_code_file` — powtórzony w wyniku, żeby stał obok
    zakresu oddanego (`ReturnedLines`). To jedyne narzędzie, które może oddać inny zakres niż
    żądany, więc różnicę ma być widać w samym wyniku, bez sięgania do wywołania.
    """

    model_config = ConfigDict(extra="forbid")

    from_line: int        = Field(ge=1, examples=[1])
    # `None` znaczy, że agent prosił o plik do końca.
    to_line:   int | None = Field(ge=1, examples=[500])


class ReturnedLines(BaseModel):
    """
    Description:
    Zakres linii, który `read_code_file` naprawdę oddało, i dwa powody, dla których bywa krótszy
    od żądanego: limit linii na wywołanie albo koniec pliku. Obie flagi naraz nie są prawdziwe;
    obie fałszywe znaczą, że agent dostał dokładnie żądany zakres, a plik ma dalsze linie.
    """

    model_config = ConfigDict(extra="forbid")

    from_line:    int  = Field(ge=1, examples=[1])
    to_line:      int  = Field(ge=1, examples=[300])
    # Limit urwał odczyt przed końcem żądanego zakresu: dalsze linie czyta się od `to_line` + 1.
    cut_by_limit: bool = Field(examples=[True])
    # Oddany zakres kończy się na ostatniej linii pliku: dalej nic nie ma.
    end_of_file:  bool = Field(examples=[False])


class CodeLine(BaseModel):
    """
    Description:
    Jedna linia pliku oddana przez `read_code_file`: numer i treść. Pola nazywają się jak
    w wyniku `find_code_text`, a numer wraca w kształcie, w jakim model poda go `quote_code`.
    """

    model_config = ConfigDict(extra="forbid")

    line: int = Field(ge=1, examples=[18])
    # Znak w znak, z wcięciem: w odczycie wcięcie pokazuje, w którym bloku linia leży.
    text: str = Field(examples=["        if (!$sekwencja) {"])


class ReadCodeFileResult(BaseModel):
    """
    Description:
    Co daje jeden odczyt `read_code_file`: ścieżka pliku, jego długość, zakres żądany, zakres
    oddany i linie z numerami. Ścieżka wraca w jednej postaci — względna wobec kodu aplikacji,
    bez `..` — tej samej, którą przyjmuje `quote_code`.

    Zakresy są dwa, bo zwykle się zgadzają, ale nie zawsze: prośbę o linie 12–40 pliku na 14
    linii kończy plik, a prośbę o cały plik na 441 linii urywa limit.
    """

    model_config = ConfigDict(extra="forbid")

    path:      str            = Field(min_length=1, examples=["src/lib/Urzad/Http/Klient.php"])
    file_info: CodeFileInfo
    requested: RequestedLines
    returned:  ReturnedLines
    # Nigdy pusta: odczyt, który nie ma ani jednej linii do oddania, kończy się błędem.
    lines:     list[CodeLine] = Field(min_length=1)
