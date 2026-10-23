from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenQuery:
    """Zapytanie golden setu: słowa zgłaszającego i ten sam tekst w polach narzędzia."""

    query_raw:      str  # zgłoszenie słowami użytkownika, bez przyczyny i słów z rozwiązania
    query_problem:  str  # pole `problem` narzędzia `find_tickets_vector`, napisane z `query_raw`
    query_symptoms: str  # pole `symptoms` tego narzędzia, napisane z `query_raw`
    kind:           str  # warstwa: „eksploatacyjne” albo „wdrożeniowo-migracyjne”
    difficulty:     str  # warstwa: „typowe” albo „trudne”
