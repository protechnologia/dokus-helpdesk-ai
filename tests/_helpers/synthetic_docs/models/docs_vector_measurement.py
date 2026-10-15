import dataclasses


@dataclasses.dataclass(frozen=True)
class DocsVectorMeasurement:
    """Wynik jednego przejścia zestawu `find_docs_vector` przez narzędzie."""

    expected_first:       int  # zapytania z odpowiedzią, na które oczekiwana sekcja jest pierwsza
    distractors_below:    int  # dystraktory niżej niż najlepsza oczekiwana sekcja albo nieobecne
    distractors_total:    int  # wszystkie dystraktory zestawu
    unanswered_with_hits: int  # zapytania bez odpowiedzi z co najmniej jedną sekcją
