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
    """Metryczka z sekcjami nie po alfabecie → spis w kolejności metryczki: miejsce sekcji
    w dokumencie zapisuje indeksacja, a układa po nim baza."""
    result = await docs_index.listing.load()

    assert [section.section_id for section in result.sections] == list(docs_index.bodies)


async def test_every_listed_section_carries_its_release_and_chapter(docs_index) -> None:
    """Metryczka dokumentu → każda sekcja spisu z dokumentem, wydaniem, datą i rozdziałem jako
    listą: data i ścieżka rozdziału przechodzą przez kolumny bazy i wracają w swoich typach."""
    result = await docs_index.listing.load()

    for section in result.sections:
        assert section.document     == "Instrukcja biura"
        assert section.version      == "1.0"
        assert section.date         == date(2026, 10, 5)
        assert section.chapter_path == ["Biuro"]
