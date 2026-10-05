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
    """Sprawdza, czy wyszukiwanie po słowach znajduje sekcję także wtedy, gdy słowa w zapytaniu
    mają inną odmianę niż w treści: „hipopotamy kwiaty" trafia w sekcję ze zdaniem o hipopotamie
    podlewającym kwiaty, i tylko w nią.

    Wyłapuje bazę bez polskiego słownika albo z zepsutą konfiguracją wyszukiwania: odmianę słów
    zna słownik bazy, nie nasz kod, więc bez niego agent musiałby trafić w dokładną formę słowa."""
    # "Hipopotam odpowiada za podlewanie kwiatów w sekretariacie."
    result = await docs_index.text.find(FindDocsTextQuery(words="hipopotamy kwiaty"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-zwierzeta", "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_message_broken_across_lines_is_found_as_a_phrase(docs_index) -> None:
    """Sprawdza, czy komunikat zapisany w treści sekcji w dwóch liniach (złamany po „Uruchom
    program") da się znaleźć frazą wpisaną w jednej linii i małymi literami.

    Wyłapuje wyszukiwanie dosłowne, któremu przeszkadza złamanie linii albo wielkość liter:
    agent nie znalazłby komunikatu przepisanego z ekranu, choć stoi on w dokumentacji."""
    result = await docs_index.text.find(FindDocsTextQuery(exact="uruchom program odkamieniania"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa", "exact"),
    ]


async def test_a_phrase_and_words_bring_their_own_sections(docs_index) -> None:
    """Sprawdza, czy fraza i słowa podane w jednym zapytaniu szukają niezależnie: kod „KAW-17"
    trafia w jedną sekcję, słowa „recepcje parkingowe" w inną, a wynik niesie obie, z sekcją
    znalezioną frazą na pierwszym miejscu.

    Wyłapuje połączenie obu pól w jeden warunek albo pomyloną kolejność: zapytanie, w którym
    fraza i słowa dotyczą różnych sekcji, nie zwracałoby wtedy nic albo stawiałoby trafienie
    dosłowne za słownym."""
    result = await docs_index.text.find(
        FindDocsTextQuery(exact="KAW-17", words="recepcje parkingowe")
    )

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa",    "exact"),
        ("usr-parking", "words"),
    ]
