"""
Description:
Test integracyjny narzędzia `find_docs_vector` z prawdziwym embedderem, Qdrantem i Postgresem:
czy sekcje zapisane przez indeksację dokumentacji da się znaleźć po znaczeniu. Wymaga działającego
stacku.

| scenariusz                        | oczekiwanie                           |
|-----------------------------------|---------------------------------------|
| pytanie innymi słowami niż sekcja | ta sekcja pierwsza                    |
| sekcja pocięta na trzy fragmenty  | wraca raz, obok pozostałych sekcji    |

Indeks buduje fixture `docs_index` z `conftest.py` tego folderu: trzy zmyślone sekcje
zaindeksowane produkcyjnym `DocsIndexer`.

O czym pamiętać przy zmianach:

- Asercje są na ranking i na to, co wróciło, nigdy na wysokość podobieństwa; próg jest wyłączony.
- Tryb embeddera, grupowanie fragmentów i liczenie progu sprawdzają testy jednostkowe na
  podmienionym transporcie; trafność na całej paczce syntetycznej to sprawa testów ewaluacyjnych.
"""

import pytest

from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


async def test_a_question_in_other_words_finds_the_section_first(docs_index) -> None:
    """Pytanie innymi słowami niż treść sekcji → ta sekcja na pierwszym miejscu. Asercja na
    ranking, nie na wysokość podobieństwa."""
    # "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej."
    result = await docs_index.vector.find(FindDocsVectorQuery(text="gdzie zarezerwować parking"))

    assert result.sections[0].section.section_id == "usr-parking"


async def test_a_section_of_several_fragments_comes_back_once(docs_index) -> None:
    """Sekcja pocięta na trzy fragmenty → w wyniku raz, a pozostałe sekcje obok niej: jednostką
    wyniku jest sekcja, którą da się odczytać, nie fragment."""
    # "Żyrafa wymienia żarówki w lampach pod sufitem."
    result = await docs_index.vector.find(
        FindDocsVectorQuery(text="kto wymienia żarówki pod sufitem")
    )
    found = [item.section.section_id for item in result.sections]

    assert found[0]      == "adm-zwierzeta"
    assert sorted(found) == sorted(docs_index.bodies)
