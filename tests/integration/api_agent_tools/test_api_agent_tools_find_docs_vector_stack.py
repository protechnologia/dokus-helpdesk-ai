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
    """Sprawdza, czy pytanie zadane innymi słowami niż treść sekcji („gdzie zarezerwować parking")
    stawia sekcję o rezerwacji miejsca parkingowego na pierwszym miejscu wyniku. Liczy się
    kolejność, nie wysokość podobieństwa.

    Wyłapuje rozjazd między indeksacją a wyszukiwaniem na prawdziwym embedderze i Qdrancie:
    gdyby sekcje zapisywano inaczej, niż się ich potem szuka, na pierwszym miejscu stanęłaby
    sekcja bez związku z pytaniem."""
    # "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej."
    result = await docs_index.vector.find(FindDocsVectorQuery(text="gdzie zarezerwować parking"))

    assert result.sections[0].section.section_id == "usr-parking"


async def test_a_section_of_several_fragments_comes_back_once(docs_index) -> None:
    """Sprawdza, czy sekcja pocięta przy indeksacji na trzy fragmenty wraca w wyniku raz, na
    pierwszym miejscu, a obok niej stoją dwie pozostałe sekcje.

    Wyłapuje wynik liczony we fragmentach zamiast w sekcjach: jedna sekcja zajęłaby wtedy kilka
    miejsc i wypchnęła z wyniku inne, a agent ma dostać sekcję, którą da się odczytać, nie jej
    fragment."""
    # "Żyrafa wymienia żarówki w lampach pod sufitem."
    result = await docs_index.vector.find(
        FindDocsVectorQuery(text="kto wymienia żarówki pod sufitem")
    )
    found = [item.section.section_id for item in result.sections]

    assert found[0]      == "adm-zwierzeta"
    assert sorted(found) == sorted(docs_index.bodies)
