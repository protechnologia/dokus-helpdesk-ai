import pytest

from anonymizer_app.core_patterns.regon import find_regon_9_by_checksum, find_regon_14_by_checksum
from tests._helpers.patterns import Variant, replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param(find_regon_9_by_checksum, "431025874", "{REGON}", id="9-cyfr"),
    pytest.param(find_regon_9_by_checksum, "REGON431025874", "REGON{REGON}", id="sklejony"),
    pytest.param(find_regon_14_by_checksum, "43102587400016", "{REGON}", id="14-cyfr"),
    pytest.param(
        find_regon_14_by_checksum,
        "dla oddziału REGON 43102587400016.",
        "dla oddziału REGON {REGON}.",
        id="14-cyfr-w-zdaniu",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param(find_regon_9_by_checksum, "431025875", id="9-cyfr-bledna-suma"),
    pytest.param(find_regon_9_by_checksum, "1431025874", id="9-cyfr-w-dluzszym-ciagu"),
    pytest.param(find_regon_14_by_checksum, "43102587400010", id="14-cyfr-bledna-suma"),
    pytest.param(find_regon_14_by_checksum, "143102587400016", id="14-cyfr-w-dluzszym-ciagu"),
]


@pytest.mark.parametrize(("variant", "text", "expected"), REPLACED)
def test_a_regon_variant_replaces_its_number(variant: Variant, text: str, expected: str) -> None:
    """Sprawdza, czy każdy wariant wzorca REGON zamienia na znacznik numer z poprawną sumą:
    9 cyfr podmiotu i 14 cyfr jednostki lokalnej, także sklejony z etykietą.

    Wyłapuje REGON, który przechodzi przez anonimizację do modelu zewnętrznego, na przykład po
    pomyleniu wag w sumie kontrolnej jednego z wariantów."""
    assert replaced_by(variant, text) == expected


@pytest.mark.parametrize(("variant", "text"), KEPT)
def test_a_regon_variant_leaves_lookalikes(variant: Variant, text: str) -> None:
    """Sprawdza, czy warianty wzorca REGON zostawiają liczby tej samej długości z błędną sumą
    i numer z poprawną sumą wewnątrz dłuższego ciągu cyfr.

    Wyłapuje wzorzec, który zamienia identyfikatory transakcji w kształcie REGON-u: wiedza
    z wątku znika, choć danej w niej nie ma."""
    assert replaced_by(variant, text) == text
