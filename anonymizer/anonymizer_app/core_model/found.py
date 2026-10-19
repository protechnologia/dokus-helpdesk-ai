import re

from pydantic import BaseModel, ConfigDict


class Found(BaseModel):
    """
    Description:
    Jedno miejsce w tekście, które wzorzec uznał za daną: rodzaj i zakres znaków. Zakres liczy
    się jak wycinek napisu w Pythonie (`text[start:end]`), więc zamiana nie musi niczego
    przeliczać.
    """

    model_config = ConfigDict(frozen=True)

    kind:  str  # rodzaj danej, zarazem nazwa znacznika bez nawiasów, np. "PESEL"
    start: int  # pozycja pierwszego znaku danej, np. 12
    end:   int  # pozycja za ostatnim znakiem danej, np. 23

    @classmethod
    def from_match(
        cls,
        kind:  str,                # np. "PESEL"
        match: re.Match[str],      # np. dopasowanie „PESEL 85030512843”
        group: str | int = 0,      # np. "value" — część dopasowania, która jest daną
    ) -> "Found":
        """
        Description:
        Buduje miejsce z dopasowania wyrażenia regularnego. Grupa wskazuje, która część
        dopasowania jest daną: etykieta („PESEL”, „ul.”) zostaje wtedy w tekście.

        Example args:
            kind="PESEL"
            match=re.search(r"PESEL (?P<value>\\d{11})", "nr PESEL 85030512843")
            group="value"

        Example result:
            Found(kind="PESEL", start=9, end=20)
        """
        found = cls(
            kind  = kind,
            start = match.start(group),
            end   = match.end(group),
        )

        return found
