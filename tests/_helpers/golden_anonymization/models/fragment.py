import dataclasses


@dataclasses.dataclass(frozen=True)
class Fragment:
    """Jeden zaznaczony fragment przypadku: dana, która ma zniknąć, albo wiedza, która ma zostać."""

    kind:   str  # rodzaj, np. "NAZWISKO" albo "KOD_BŁĘDU"
    text:   str  # fragment tak, jak stoi w tekście, np. "Wiśniewska"
    number: int  # kolejny numer fragmentu w jego rodzaju w przypadku, od 1, np. 2

    def shown(
        self,
        synthetic: bool,  # np. False — przypadek z próbki korpusu
    ) -> str:
        """
        Description:
        Nazwa fragmentu w ocenie i w komunikatach testów. Przy zestawie zmyślonym to sam fragment,
        przy próbce korpusu rodzaj z numerem, bo fragment jest daną klienta, a komunikat trafia
        do konsoli.

        Example args:
            synthetic=False

        Example result:
            "NAZWISKO nr 2"
        """
        # --- zestaw zmyślony: fragment można pokazać ---
        if synthetic:
            return f"{self.kind} „{self.text}”"

        return f"{self.kind} nr {self.number}"
