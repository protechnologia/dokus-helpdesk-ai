import dataclasses


@dataclasses.dataclass(frozen=True)
class PolishCase:
    """Jedna sprawa „Popraw” z zestawu: notatki i to, co ma się z nimi stać."""

    case_id:    str              # np. "s01"
    phenomenon: str              # np. "słowa potoczne i liczba w notatkach"
    text:       str              # notatki wdrożeniowca, np. "przesylki juz ida…"
    colloquial: tuple[str, ...]  # rdzenie słów potocznych, które mają zniknąć, np. ("smig",)
    kept:       tuple[str, ...]  # fakty, które mają zostać, np. ("17",)
    tempting:   tuple[str, ...]  # pułapki: dopiski, których nie ma w notatkach, np. ("menu",)

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "s01 słowa potoczne i liczba w notatkach"
        """
        return f"{self.case_id} {self.phenomenon}"
