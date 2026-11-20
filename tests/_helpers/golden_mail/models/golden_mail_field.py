import dataclasses


@dataclasses.dataclass(frozen=True)
class GoldenMailField:
    """Jedno pole wątku golden setu (opis albo komentarz): autor wiadomości z 32.1 i oznaczenia
    linii z 32.3 — po etykiecie na linię ze słowami, w kolejności — ze skrótem tekstu pola,
    z którego je zrobiono."""

    author: str              # np. "dostawca" — klient, dostawca, system albo brak (puste pole)
    digest: str              # np. "76d7671201f1a6c8" — skrót tekstu pola z `message_texts()`
    labels: tuple[str, ...]  # np. ("tresc", "tresc", "podpis", "kopia")
