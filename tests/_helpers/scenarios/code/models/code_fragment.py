import dataclasses


@dataclasses.dataclass(frozen=True)
class CodeFragment:
    """Fragment pliku kodu: ścieżka i zakres linii, obie granice włącznie."""

    path:      str  # np. "src/lib/Urzad/Wysylka/Edoreczenia/PobieranieSkrzynki.php"
    from_line: int  # np. 35
    to_line:   int  # np. 37

    @property
    def key(self) -> str:
        """
        Description:
        Zapis fragmentu jak `item_id` źródła z kodu: ścieżka i zakres linii.

        Example args:
            (brak)

        Example result:
            "src/lib/Urzad/Wysylka/Edoreczenia/PobieranieSkrzynki.php:35-37"
        """
        return f"{self.path}:{self.from_line}-{self.to_line}"

    def overlaps(
        self,
        other: "CodeFragment",  # np. CodeFragment(path="…/PobieranieSkrzynki.php", 33, 38)
    ) -> bool:
        """
        Description:
        Czy dwa fragmenty dzielą choć jedną linię tego samego pliku.

        Example args:
            other=CodeFragment(path="…/PobieranieSkrzynki.php", from_line=33, to_line=38)

        Example result:
            True
        """
        overlap = (
            self.path == other.path
            and self.from_line <= other.to_line
            and other.from_line <= self.to_line
        )

        return overlap
