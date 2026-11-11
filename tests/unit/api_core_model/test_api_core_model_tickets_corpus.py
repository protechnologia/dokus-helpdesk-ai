from pathlib import Path

from app.core_model.tickets.tickets_corpus import TicketsCorpus

# Układ katalogu korpusu zgłoszeń: nazwy podkatalogów są umową z dyskiem i z montowaniami
# w `docker-compose.prod.yml`, więc test zapisuje je wprost.


def test_the_subdirectories_keep_their_names() -> None:
    """Sprawdza, czy podkatalogi korpusu nazywają się `cards`, `anonymized`, `raw-db`
    i `raw-route` i leżą bezpośrednio w katalogu korpusu.

    Wyłapuje zmianę nazwy podkatalogu w kodzie bez przeniesienia danych na dysku i bez poprawki
    montowań na prod: trasa pisałaby wtedy karty do katalogu, którego kontener nie zachowuje,
    a indeks budowałby się z pustego miejsca."""
    corpus = TicketsCorpus(root=Path("/korpus"))

    assert corpus.cards_dir      == Path("/korpus/cards")
    assert corpus.anonymized_dir == Path("/korpus/anonymized")
    assert corpus.raw_db_dir     == Path("/korpus/raw-db")
    assert corpus.raw_route_dir  == Path("/korpus/raw-route")
