"""
Description:
Test integracyjny narzędzia `list_docs` z prawdziwym Postgresem: czy spis treści oddaje sekcje
zapisane przez indeksację dokumentacji, w kolejności dokumentu i z opisem z metryczki. Wymaga
działającego stacku.

| scenariusz                              | oczekiwanie                          |
|-----------------------------------------|--------------------------------------|
| sekcje w metryczce nie po alfabecie     | spis w kolejności metryczki          |
| metryczka z wydaniem, datą i rozdziałem | każda sekcja spisu niesie je w opisie |

Indeks buduje fixture `docs_index` z `conftest.py` tego folderu: trzy zmyślone sekcje
zaindeksowane produkcyjnym `DocsIndexer` — stąd markery embeddera i Qdranta, choć samo narzędzie
pyta tylko Postgresa.

O czym pamiętać przy zmianach:

- Miejsce sekcji w dokumencie zapisuje indeksacja, a układa po nim baza; narzędzie niczego nie
  sortuje — dlatego kolejności nie da się sprawdzić bez obu.
- Zgodność spisu z całą paczką syntetyczną to sprawa testów ewaluacyjnych.
"""

from datetime import date

import pytest

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


async def test_the_listing_follows_the_manifest_not_the_alphabet(docs_index) -> None:
    """Sprawdza, czy spis treści podaje sekcje w kolejności, w jakiej stoją w metryczce dokumentu,
    a nie alfabetycznie: w teście metryczka wymienia je celowo nie po alfabecie.

    Wyłapuje zgubienie kolejności po drodze: miejsce sekcji w dokumencie zapisuje indeksacja,
    a układa według niego baza, więc gdyby któraś z nich przestała to robić, agent dostałby spis
    treści w innym porządku niż dokument."""
    result = await docs_index.listing.load()

    assert [section.section_id for section in result.sections] == list(docs_index.bodies)


async def test_every_listed_section_carries_its_release_and_chapter(docs_index) -> None:
    """Sprawdza, czy każda sekcja w spisie treści niesie dane z metryczki dokumentu: jego nazwę,
    wydanie, datę i ścieżkę rozdziału — datę jako datę, a ścieżkę jako listę.

    Wyłapuje dane, które po drodze przez kolumny bazy giną albo wracają w innym typie, na
    przykład data jako napis: agent nie wiedziałby wtedy, do którego wydania instrukcji należy
    sekcja."""
    result = await docs_index.listing.load()

    for section in result.sections:
        assert section.document     == "Instrukcja biura"
        assert section.version      == "1.0"
        assert section.date         == date(2026, 10, 5)
        assert section.chapter_path == ["Biuro"]
