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
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.agent_tools.docs.find_docs_text import (
    FindDocsTextQuery,
    FindDocsTextResult,
    FindDocsTextTool,
)
from app.config import Settings
from app.core_service.factory_docs_indexer import docs_index_names
from app.db_postgres import DbPostgresError, DocsTable
from tests.conftest import build_host_settings, build_postgres_client

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]

GOLDEN_FILE = Path("data/safe/golden/docs-synthetic.json")

# Zapytania zestawu, czytane przy imporcie: z nich powstają parametry testów.
ENTRIES = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["find_docs_text"]

BUILD_HINT = (
    "zbuduj indeks syntetyczny: "
    "docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes"
)


async def _search_all(
    settings: Settings,  # np. Settings(rag_top_k=5, …)
) -> dict[str, FindDocsTextResult]:
    """
    Description:
    Przepuszcza wszystkie zapytania zestawu przez `FindDocsTextTool` na indeksie syntetycznym,
    z limitem z konfiguracji, i oddaje wyniki po identyfikatorze zapytania. Tabela, której nie
    ma, wywala test z podpowiedzią, jak ją zbudować.

    Example args:
        settings=Settings(rag_top_k=5, …)

    Example result:
        {"t01": FindDocsTextResult(sections=[MatchedSection(…)], omitted_over_limit=0), …}
    """
    table_name, _ = docs_index_names(settings, synthetic=True)

    tool = FindDocsTextTool(
        docs  = DocsTable(build_postgres_client(), name=table_name),
        limit = settings.rag_top_k,
    )

    try:
        results = {
            entry["id"]: await tool.find(FindDocsTextQuery(**entry["query"]))
            for entry in ENTRIES
        }
    except DbPostgresError as exc:
        # Brak tabeli wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")
    finally:
        await tool.aclose()

    return results


@pytest.fixture(scope="module")
def results() -> dict[str, FindDocsTextResult]:
    """
    Description:
    Odpytuje indeks raz na cały plik: jedno połączenie z bazą na 32 zapytania.

    Example args:
        (brak)

    Example result:
        {"t01": FindDocsTextResult(…), "t02": FindDocsTextResult(…), …}
    """
    return asyncio.run(_search_all(build_host_settings()))


@pytest.mark.parametrize(
    "entry",
    ENTRIES,
    ids=lambda entry: f"{entry['id']}-{entry['phenomenon']}",
)
def test_a_query_finds_what_its_entry_declares(
    entry:   dict,
    results: dict[str, FindDocsTextResult],
) -> None:
    """Zapytanie zestawu → oczekiwane sekcje z etykietą, bez sekcji niechcianych i z łączną
    liczbą pasujących zgodną z wpisem."""
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
