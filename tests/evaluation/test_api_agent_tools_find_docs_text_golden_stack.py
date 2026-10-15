"""
Description:
Test ewaluacyjny narzędzia `find_docs_text` na zestawie zapytań paczki syntetycznej: czy fraza
i słowa znajdują dokładnie te sekcje, które mają znaleźć, z właściwą etykietą i licznikiem.
Wymaga działającego stacku z zaindeksowaną paczką.

Każde z 32 zapytań zestawu jest osobnym testem i sprawdza to, co jego wpis deklaruje:

| pole wpisu       | co sprawdza test                                              |
|------------------|---------------------------------------------------------------|
| `expected`       | każda z tych sekcji wróciła, z podaną etykietą `matched_by`   |
| `not_expected`   | żadna z tych sekcji nie wróciła                               |
| `expected_total` | zwrócone i pominięte ponad limit dają razem tyle sekcji       |

Po co: zestaw zbiera przypadki, na których wyszukiwanie tekstowe psuje się po cichu — odmiana,
zaprzeczenie, nazwy własne, wyrazy z łącznikiem, kody sklejone z interpunkcją, znaki wzorca,
komunikat złamany między liniami. Każdy zależy od słownika i SQL-a po stronie bazy, więc bez niej
nie da się go sprawdzić.

O czym pamiętać przy zmianach:

- Tu nie ma progów „prawie wszystkie": dopasowanie tekstowe nie zależy od modelu, więc każde
  zapytanie ma dać dokładnie to, co deklaruje.
- Zapytań i oczekiwań nie wolno poprawiać pod wynik. Sekcje poza `expected` wolno narzędziu
  zwrócić — wykaz uprawnień zawiera większość słów kluczowych paczki.
- Indeksem jest syntetyczny indeks z konfiguracji. Buduje go
  `docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes`; tabelę
  założoną przed zmianą kolumny `search_text` trzeba zbudować ponownie.
- Przed pomiarem fixture `synthetic_docs_table` z `conftest.py` sprawdza, że tabela indeksu ma
  dokładnie sekcje paczki z treścią jak w plikach; nieaktualny indeks kończy pomiar błędem.
- Odpytanie indeksu leży w `tests/_helpers/synthetic_docs/`.
"""

import asyncio

import pytest

from app.agent_tools.docs.find_docs_text import FindDocsTextResult
from tests._helpers.synthetic_docs import BUILD_HINT, docs_text_entries, search_docs_text
from tests.conftest import build_host_settings

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]

# Zapytania zestawu, czytane przy imporcie: z nich powstają parametry testów.
ENTRIES = docs_text_entries()


@pytest.fixture(scope="module")
def results(
    synthetic_docs_table: None,  # warunek z conftest.py: tabela odpowiada plikom paczki
) -> dict[str, FindDocsTextResult]:
    """
    Description:
    Odpytuje indeks raz na cały plik: jedno połączenie z bazą na 32 zapytania. Najpierw warunek
    `synthetic_docs_table` sprawdza, że indeks odpowiada paczce — inaczej wynik byłby nieważny.

    Example args:
        synthetic_docs_table=None

    Example result:
        {"t01": FindDocsTextResult(…), "t02": FindDocsTextResult(…), …}
    """
    return asyncio.run(search_docs_text(build_host_settings()))


@pytest.mark.parametrize(
    "entry",
    ENTRIES,
    ids=lambda entry: f"{entry['id']}-{entry['phenomenon']}",
)
def test_a_query_finds_what_its_entry_declares(
    entry:   dict,
    results: dict[str, FindDocsTextResult],
) -> None:
    """Sprawdza jedno zapytanie zestawu: czy wyszukiwanie po frazie i po słowach znalazło sekcje,
    które miało znaleźć, nie znalazło tych, których nie powinno, i naliczyło tyle pasujących, ile
    jest w paczce.

    Wyłapuje błędy słownika i dopasowania, przy których wyszukiwanie dalej działa, ale gubi albo
    dokłada trafienia — na przykład przestaje rozpoznawać odmianę słowa, myli „widoczne"
    z „niewidoczne" albo nie znajduje fragmentu kodu błędu."""
    result = results[entry["id"]]
    found  = {item.section.section_id: item.matched_by for item in result.sections}

    for expected in entry["expected"]:
        assert found.get(expected["section_id"]) == expected["matched_by"], (
            f"{entry['id']}: brak {expected['section_id']} jako {expected['matched_by']} "
            f"(wróciło: {found}) — {BUILD_HINT}"
        )

    for section_id in entry.get("not_expected", []):
        assert section_id not in found, f"{entry['id']}: wróciła niechciana sekcja {section_id}"

    if "expected_total" in entry:
        total = len(result.sections) + result.omitted_over_limit

        assert total == entry["expected_total"], (
            f"{entry['id']}: pasuje {total} sekcji, oczekiwane {entry['expected_total']}"
        )
