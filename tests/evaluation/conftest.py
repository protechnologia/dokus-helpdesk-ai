"""
Description:
Warunki wstępne pomiarów na paczce syntetycznej. Testy ewaluacyjne dokumentacji mierzą
wyszukiwanie na indeksie syntetycznym zbudowanym wcześniej na stacku; fixture'y stąd sprawdzają
przed pomiarem, że ten indeks odpowiada plikom paczki i dzisiejszej konfiguracji.

| fixture                     | co sprawdza                  | pyta     | pomiar             |
|-----------------------------|------------------------------|----------|--------------------|
| `synthetic_docs_table`      | sekcje paczki i ich treść    | Postgres | `find_docs_text`   |
| `synthetic_docs_collection` | punktów tyle, ile fragmentów | Qdrant   | `find_docs_vector` |

Po co: nieaktualny indeks nie znaczy „niska skuteczność", tylko „pomiar jest nieważny". Dlatego
to nie są testy z własnym wynikiem, tylko warunek pomiaru: gdy indeks nie odpowiada paczce,
pomiar kończy się błędem z podpowiedzią, jak indeks zbudować, zamiast podać liczby zmierzone na
czymś innym niż pliki. Porównanie indeksu z paczką leży w `tests/_helpers/synthetic_docs/`.
"""

import asyncio

import pytest

from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from tests._helpers.synthetic_docs import (
    BUILD_HINT,
    collection_differences,
    require_no_differences,
    table_differences,
)
from tests.conftest import build_host_settings


@pytest.fixture(scope="module")
def synthetic_docs_table() -> None:
    """
    Description:
    Warunek pomiaru wyszukiwania tekstowego: tabela indeksu syntetycznego ma dokładnie sekcje
    paczki, w kolejności dokumentów, z treścią znak w znak jak w plikach. Tabela, której nie ma,
    i tabela nieaktualna kończą pomiar błędem z podpowiedzią, jak zbudować indeks.

    Example args:
        (brak)

    Example result:
        None — tabela odpowiada paczce
    """
    try:
        differences = asyncio.run(table_differences(build_host_settings()))
    except DbPostgresError as exc:
        # Brak tabeli wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")

    require_no_differences(differences)


@pytest.fixture(scope="module")
def synthetic_docs_collection() -> None:
    """
    Description:
    Warunek pomiaru wyszukiwania po znaczeniu: kolekcja indeksu syntetycznego ma tyle punktów, na
    ile fragmentów tnie paczkę dzisiejsza konfiguracja. Kolekcja, której nie ma, i kolekcja
    sprzed zmiany cięcia kończą pomiar błędem z podpowiedzią, jak zbudować indeks.

    Example args:
        (brak)

    Example result:
        None — kolekcja odpowiada paczce
    """
    try:
        differences = asyncio.run(collection_differences(build_host_settings()))
    except DbQdrantError as exc:
        # Brak kolekcji wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")

    require_no_differences(differences)
