from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Najwyżej tyle linii ma jeden cytowany fragment: źródłem ma być miejsce — warunek, ustawienie,
# treść komunikatu — a nie cała metoda ani plik.
MAX_LINES_PER_QUOTE = 40

# Po co model cytuje fragment. `cause`: ten kod powoduje zachowanie opisane w zgłoszeniu.
# `excluded`: miejsce sprawdzone i wykluczone jako przyczyna.
QuoteRole = Literal["cause", "excluded"]


class QuoteCodeQuery(BaseModel):
    """
    Description:
    O co agent prosi `quote_code`: jeden fragment pliku z kodu aplikacji, od linii do linii
    włącznie, i rola tego fragmentu w sprawie.

    Jeden fragment na wywołanie, nie lista: limit wywołań narzędzia jest wtedy wprost limitem
    cytowań w jednej sprawie. Rola jest wymagana i nie ma wartości domyślnej — od niej zależy,
    czy fragment trafi na listę źródeł, więc model ma ją podać świadomie.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    path:      str       = Field(min_length=1, examples=["src/lib/Urzad/Numeracja/Generator.php"])
    # Numery linii liczone od 1, obie granice należą do fragmentu.
    from_line: int       = Field(ge=1, examples=[14])
    to_line:   int       = Field(ge=1, examples=[19])
    role:      QuoteRole = Field(examples=["cause"])

    @model_validator(mode="after")
    def _fragment_is_ordered_and_short(self) -> Self:
        """
        Description:
        Odrzuca fragment, który kończy się przed swoim początkiem, i fragment dłuższy niż
        `MAX_LINES_PER_QUOTE`. Oba błędy wracają do modelu jako błędne argumenty, z liczbami.

        Example args:
            (brak)

        Example result:
            QuoteCodeQuery(path="src/lib/…/Generator.php", from_line=14, to_line=19, role="cause")

        Raises:
            ValueError: `to_line` mniejsze niż `from_line` albo fragment ponad limit linii
        """
        # --- koniec przed początkiem ---
        if self.to_line < self.from_line:
            raise ValueError(
                f"to_line ({self.to_line}) jest mniejsze niż from_line ({self.from_line})"
            )

        lines = self.to_line - self.from_line + 1

        # --- fragment za długi na jedno cytowanie ---
        if lines > MAX_LINES_PER_QUOTE:
            raise ValueError(
                f"fragment ma {lines} linii, a cytowanie najwyżej {MAX_LINES_PER_QUOTE} — "
                f"zacytuj samo miejsce, które pokazuje przyczynę"
            )

        return self


class QuoteCodeResult(BaseModel):
    """
    Description:
    Co daje jedno cytowanie `quote_code`: potwierdzenie, który fragment został zapisany i w jakiej
    roli. Ścieżka wraca w jednej postaci — względna wobec kodu aplikacji, bez `..`.

    Treści linii tu nie ma, celowo: narzędzie, które ją oddaje, służy modelowi za odczyt i kusi
    do cytowania linii, których nie przeczytał. Treść daje wyłącznie odczyt.
    """

    model_config = ConfigDict(extra="forbid")

    path:      str       = Field(min_length=1, examples=["src/lib/Urzad/Numeracja/Generator.php"])
    from_line: int       = Field(ge=1, examples=[14])
    to_line:   int       = Field(ge=1, examples=[19])
    role:      QuoteRole = Field(examples=["cause"])
