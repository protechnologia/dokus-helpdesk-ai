import dataclasses


@dataclasses.dataclass
class MailLabelCounts:
    """Ile linii i słów jednej etykiety zostało po czyszczeniu, a ile zniknęło."""

    kept_lines:    int = 0  # linie, które zostały
    removed_lines: int = 0  # linie, które czyszczenie usunęło
    kept_words:    int = 0  # słowa w liniach, które zostały
    removed_words: int = 0  # słowa w liniach, które czyszczenie usunęło
