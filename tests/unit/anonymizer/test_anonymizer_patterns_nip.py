import pytest

from anonymizer_app.core_patterns.nip import find_nip_by_checksum
from tests._helpers.patterns import replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param("7421365180", "{NIP}", id="ciagiem"),
    pytest.param("NIP 742-136-51-80,", "NIP {NIP},", id="3-3-2-2-myslniki"),
    pytest.param("742 136 51 80", "{NIP}", id="3-3-2-2-spacje"),
    pytest.param("742 136-51 80", "{NIP}", id="odstepy-mieszane"),
    pytest.param("742-136-5180", "{NIP}", id="czesc-odstepow"),
    pytest.param("742-13-65-180", "{NIP}", id="3-2-2-3"),
    pytest.param("954\xa0287\xa013\xa039", "{NIP}", id="twarde-spacje"),
    pytest.param("Key (nip)=(5213012076)", "Key (nip)=({NIP})", id="w-komunikacie-bazy"),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param("zamówienie nr 123-456-78-90", id="bledna-suma"),
    pytest.param("7421365181", id="zla-cyfra-kontrolna"),
    pytest.param("17421365180", id="w-dluzszym-ciagu-cyfr"),
    pytest.param("742-136-51-80-1", id="dalszy-ciag-po-myslniku"),
]


@pytest.mark.parametrize(("text", "expected"), REPLACED)
def test_the_nip_variant_replaces_every_notation(text: str, expected: str) -> None:
    """Sprawdza, czy wzorzec NIP zamienia na znacznik numer z poprawną sumą w każdym zapisie:
    ciągiem, w układzie 3-3-2-2 albo 3-2-2-3, z myślnikami, spacjami, twardymi spacjami albo
    odstępami mieszanymi, także wewnątrz komunikatu bazy danych.

    Wyłapuje zapis NIP-u, który przechodzi przez anonimizację do modelu zewnętrznego."""
    assert replaced_by(find_nip_by_checksum, text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_the_nip_variant_leaves_lookalikes(text: str) -> None:
    """Sprawdza, czy wzorzec NIP zostawia dziesięć cyfr z błędną sumą i NIP wewnątrz dłuższego
    ciągu cyfr albo myślników.

    Wyłapuje wzorzec, który zamienia numery zamówień i faktur w kształcie NIP-u: wiedza z wątku
    znika, choć danej w niej nie ma."""
    assert replaced_by(find_nip_by_checksum, text) == text

