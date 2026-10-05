"""
Description:
Test integracyjny narzędzia `read_docs` z prawdziwym Postgresem: czy identyfikatory oddane przez
spis i oba wyszukiwania dają się odczytać i czy treść wraca taka, jak ją zapisała indeksacja.
Wymaga działającego stacku.

| scenariusz                                    | oczekiwanie                       |
|-----------------------------------------------|-----------------------------------|
| sekcja znaleziona frazą złamaną w treści      | treść znak w znak, ze złamaniem   |
| sekcja pocięta na fragmenty do wektorów       | treść w całości, niepocięta       |
| ta sama sekcja ze spisu, wyszukiwań i odczytu | ten sam opis sekcji               |
| sekcja znana i nieznana w jednym zapytaniu    | błąd z nieznaną, nic częściowego  |

Indeks buduje fixture `docs_index` z `conftest.py` tego folderu: trzy zmyślone sekcje
zaindeksowane produkcyjnym `DocsIndexer`.

O czym pamiętać przy zmianach:

- Odczyt dostaje tu identyfikatory od innych narzędzi, nie wpisane w teście: sprawdzamy, że oba
  indeksy wskazują jedną sekcję, którą odczyt przyjmuje.
- Powtórzenia identyfikatorów sprawdzają testy jednostkowe na kliencie-atrapie; tu zostaje to,
  co wie tylko baza.
"""

import pytest

from app.agent_tools.docs.find_docs_text import FindDocsTextQuery
from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery
from app.agent_tools.docs.read_docs import ReadDocsQuery, UnknownSectionError

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


async def test_a_section_found_by_a_phrase_is_read_verbatim(docs_index) -> None:
    """Sekcja znaleziona frazą w jednej linii → odczyt oddaje treść znak w znak, ze złamaniem
    w środku komunikatu: wyszukiwanie widzi tekst ze spacjami, model czyta oryginał."""
    found = await docs_index.text.find(FindDocsTextQuery(exact="uruchom program odkamieniania"))
    read  = await docs_index.read.search(
        ReadDocsQuery(section_ids=[item.section.section_id for item in found.sections])
    )

    assert [item.text for item in read.sections] == [docs_index.bodies["adm-kawa"]]
    assert "Uruchom program\nodkamieniania" in read.sections[0].text


async def test_a_section_cut_into_fragments_is_read_whole(docs_index) -> None:
    """Sekcja znaleziona po jednym z trzech fragmentów → odczyt oddaje ją w całości: na fragmenty
    tnie się tylko to, co idzie do wektorów."""
    # "Żyrafa wymienia żarówki w lampach pod sufitem."
    found = await docs_index.vector.find(
        FindDocsVectorQuery(text="kto wymienia żarówki pod sufitem")
    )
    read = await docs_index.read.search(
        ReadDocsQuery(section_ids=[found.sections[0].section.section_id])
    )

    assert read.sections[0].text == docs_index.bodies["adm-zwierzeta"]
    assert [ref.item_id for ref in docs_index.read.cite(read)] == ["adm-zwierzeta"]


async def test_every_tool_describes_a_section_the_same_way(docs_index) -> None:
    """Ta sama sekcja ze spisu, z obu wyszukiwań i z odczytu → ten sam opis z metryczki: oba
    indeksy wskazują jeden identyfikator, a odczyt go przyjmuje."""
    by_meaning = await docs_index.vector.find(FindDocsVectorQuery(text="gdzie jest parking"))
    by_words   = await docs_index.text.find(FindDocsTextQuery(words="miejsce parkingowe"))
    listed     = await docs_index.listing.load()
    read       = await docs_index.read.search(ReadDocsQuery(section_ids=["usr-parking"]))

    section = read.sections[0].section

    assert by_meaning.sections[0].section == section
    assert by_words.sections[0].section   == section
    assert listed.sections[-1]            == section


async def test_an_unknown_section_among_known_ones_fails_the_whole_read(docs_index) -> None:
    """Sekcja, która jest, i sekcja, której nie ma → `UnknownSectionError` tylko z nieznaną, bez
    treści tej znanej: baza oddaje wtedy jeden wiersz bez błędu, więc o tym, że to błąd, mówi
    narzędzie."""
    with pytest.raises(UnknownSectionError) as caught:
        await docs_index.read.search(ReadDocsQuery(section_ids=["usr-parking", "usr-nie-ma"]))

    assert caught.value.section_ids == ["usr-nie-ma"]
