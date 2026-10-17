import dataclasses

from tests._helpers.golden_anonymization.models.fragment import Fragment


@dataclasses.dataclass(frozen=True)
class AnonymizationCase:
    """Jeden tekst golden setu anonimizatora: co ma z niego zniknąć i co ma w nim zostać."""

    case_id:    str                   # np. "s01"
    phenomenon: str                   # np. "podpis w dwóch liniach i adres w nawiasach <>"
    text:       str                   # tekst wejściowy, np. wątek z `RawTicket.as_thread()`
    remove:     tuple[Fragment, ...]  # dane, które mają zniknąć
    keep:       tuple[Fragment, ...]  # wiedza, która ma zostać
    synthetic:  bool                  # True — zestaw zmyślony, False — próbka korpusu
    ticket_id:  str | None            # numer zgłoszenia przy próbce korpusu, np. "34096"

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa przypadku w komunikatach: identyfikator i zjawisko. Zjawisko nie cytuje tekstu, więc
        nazwa nie niesie danych także przy próbce korpusu.

        Example args:
            (brak)

        Example result:
            "s01 podpis w dwóch liniach i adres w nawiasach <>"
        """
        return f"{self.case_id} {self.phenomenon}"
