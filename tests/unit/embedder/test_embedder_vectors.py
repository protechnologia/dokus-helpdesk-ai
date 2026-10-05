import math

import pytest

from embedder_app.encoding import deterministic_vector

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"

# Recorded output of the current algorithm. Not a magic constant to be "fixed" when it fails:
# a changed value means indexed vectors no longer match freshly computed ones, which silently
# breaks every recall assertion built on this backend. Update it only alongside a deliberate
# change to deterministic_vector — and re-index whatever was built with the old one.
GOLDEN_VECTOR_DIM_4 = [
    -0.6217898978404582,
    -0.715272348583971,
    -0.16192790798410245,
    -0.2748493094599569,
]


def test_same_text_yields_identical_vector() -> None:
    """Sprawdza, czy ten sam tekst policzony dwa razy daje dwa razy ten sam wektor.

    Wyłapuje losowość w liczeniu wektora atrapy. Cała atrapa istnieje po to, żeby tekst zawsze dawał
    ten sam wektor; bez tego żaden test wyszukiwania oparty na niej nie byłby powtarzalny."""
    assert deterministic_vector(TICKET_TEXT, 8) == deterministic_vector(TICKET_TEXT, 8)


def test_mapping_is_stable_across_code_changes() -> None:
    """Sprawdza, czy znany tekst przy wymiarze 4 daje dokładnie ten wektor, który zapisano w tym
    pliku jako wzorzec.

    Wyłapuje zmianę sposobu liczenia wektora, także taką, po której wynik różni się między
    uruchomieniami programu. Wektory zapisane wcześniej w indeksie przestałyby wtedy pasować do
    liczonych na nowo, a testy wyszukiwania na atrapie psułyby się po cichu."""
    assert deterministic_vector(TICKET_TEXT, 4) == GOLDEN_VECTOR_DIM_4


def test_different_texts_yield_different_vectors() -> None:
    """Sprawdza, czy dwa różne teksty dają różne wektory.

    Wyłapuje atrapę, która każdemu tekstowi oddaje ten sam wektor: wszystkie teksty byłyby wtedy do
    siebie jednakowo podobne i żaden test wyszukiwania niczego by nie dowodził."""
    assert deterministic_vector(TICKET_TEXT, 8) != deterministic_vector(OTHER_TICKET_TEXT, 8)


def test_vector_has_requested_dimension() -> None:
    """Sprawdza, czy wektor policzony dla wymiaru 768 ma dokładnie 768 liczb.

    Wyłapuje funkcję, która pomija albo źle stosuje podany wymiar: długość wektora jest umową
    z kolekcją w Qdrancie, która wektory innej długości odrzuca."""
    assert len(deterministic_vector(TICKET_TEXT, 768)) == 768


def test_vector_is_unit_length() -> None:
    """Sprawdza, czy wektor atrapy ma długość 1, czyli pierwiastek z sumy kwadratów jego liczb
    wynosi 1.

    Wyłapuje brak normalizacji wektora. Prawdziwy koder oddaje wektory o długości 1, więc bez niej
    wyniki podobieństwa w testach leżałyby w innym zakresie niż na produkcji, a próg odcięcia
    znaczyłby w nich co innego."""
    vector = deterministic_vector(TICKET_TEXT, 768)

    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


def test_texts_differing_only_by_diacritics_are_distinct() -> None:
    """Sprawdza, czy tekst z polskimi znakami („błąd drukarki") i ten sam tekst bez nich („blad
    drukarki") dają różne wektory.

    Wyłapuje liczenie wektora, które po drodze gubi polskie znaki, na przykład przez zamianę tekstu
    na ASCII: dwa różne teksty stawałyby się wtedy dla atrapy jednym."""
    assert deterministic_vector("błąd drukarki", 8) != deterministic_vector("blad drukarki", 8)
