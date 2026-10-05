"""
Description:
Test integracyjny narzędzia `find_docs_text` z prawdziwym Postgresem: czy sekcje zapisane przez
indeksację dokumentacji da się znaleźć po dosłownym brzmieniu i po słowach. Wymaga działającego
stacku.

| scenariusz                                | oczekiwanie                   |
|-------------------------------------------|-------------------------------|
| słowa w innej odmianie niż w treści       | sekcja znaleziona słowami     |
| komunikat złamany w treści między liniami | sekcja znaleziona frazą       |
| fraza i słowa trafiające w różne sekcje   | obie, ta z frazy pierwsza     |

Indeks buduje fixture `docs_index` z `conftest.py` tego folderu: trzy zmyślone sekcje
zaindeksowane produkcyjnym `DocsIndexer` — stąd markery embeddera i Qdranta, choć samo narzędzie
pyta tylko Postgresa.

O czym pamiętać przy zmianach:

- Łączenie dróg, etykiety i limit sprawdzają testy jednostkowe na kliencie-atrapie; tu zostaje
  to, co wie tylko baza: odmiana, wielkość liter i białe znaki.
- Przypadki psujące się po cichu (zaprzeczenie, wyrazy z łącznikiem, kody z interpunkcją) zbiera
  zestaw paczki syntetycznej — to sprawa testów ewaluacyjnych.
"""

import pytest

from app.agent_tools.docs.find_docs_text import FindDocsTextQuery

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


async def test_words_in_another_form_find_the_section(docs_index) -> None:
    """Słowa w innej odmianie niż w treści → sekcja znaleziona słowami: odmianę zna słownik bazy,
    nie nasz kod."""
    # "Hipopotam odpowiada za podlewanie kwiatów w sekretariacie."
    result = await docs_index.text.find(FindDocsTextQuery(words="hipopotamy kwiaty"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-zwierzeta", "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_message_broken_across_lines_is_found_as_a_phrase(docs_index) -> None:
    """Komunikat złamany w treści po „Uruchom program" → fraza w jednej linii go znajduje,
    także inną wielkością liter."""
    result = await docs_index.text.find(FindDocsTextQuery(exact="uruchom program odkamieniania"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa", "exact"),
    ]


async def test_a_phrase_and_words_bring_their_own_sections(docs_index) -> None:
    """Fraza z jednej sekcji i słowa z innej → obie sekcje, znaleziona frazą pierwsza: pola
    szukają niezależnie, a wyniki się sumują."""
    result = await docs_index.text.find(
        FindDocsTextQuery(exact="KAW-17", words="recepcje parkingowe")
    )

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa",    "exact"),
        ("usr-parking", "words"),
    ]
