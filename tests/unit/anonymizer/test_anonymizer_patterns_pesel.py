import pytest

from anonymizer_app.patterns.pesel import (
    find_pesel_by_checksum,
    find_pesel_with_error_after_label,
)
from tests._helpers.patterns import Variant, replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param(find_pesel_by_checksum, "92112304576", "{PESEL}", id="sam-numer"),
    pytest.param(
        find_pesel_by_checksum,
        "Pismo od pana 92112304576 przechodzi.",
        "Pismo od pana {PESEL} przechodzi.",
        id="w-zdaniu",
    ),
    pytest.param(find_pesel_by_checksum, "nr85030512840", "nr{PESEL}", id="sklejony-z-litera"),
    pytest.param(
        find_pesel_with_error_after_label,
        "Numer PESEL 85030512843 jest nieprawidłowy",
        "Numer PESEL {PESEL} jest nieprawidłowy",
        id="bledna-suma-po-etykiecie",
    ),
    pytest.param(
        find_pesel_with_error_after_label,
        "pesel: 85030512843",
        "pesel: {PESEL}",
        id="etykieta-malymi-z-dwukropkiem",
    ),
    pytest.param(
        find_pesel_with_error_after_label,
        "PESEL\xa085030512843",
        "PESEL\xa0{PESEL}",
        id="twarda-spacja-po-etykiecie",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param(find_pesel_by_checksum, "identyfikator 20260506118", id="bledna-suma"),
    pytest.param(find_pesel_by_checksum, "przesyłka 992112304576", id="w-dluzszym-ciagu-cyfr"),
    pytest.param(find_pesel_by_checksum, "85030512843", id="bledna-suma-bez-etykiety"),
    pytest.param(find_pesel_with_error_after_label, "PESEL 92112304576", id="poprawna-suma"),
    pytest.param(find_pesel_with_error_after_label, "PESEL 8503051284", id="dziesiec-cyfr"),
    pytest.param(find_pesel_with_error_after_label, "nr 85030512843", id="bez-etykiety"),
]


@pytest.mark.parametrize(("variant", "text", "expected"), REPLACED)
def test_a_pesel_variant_replaces_its_number(variant: Variant, text: str, expected: str) -> None:
    """Sprawdza, czy każdy wariant wzorca PESEL zamienia na znacznik sam numer, który ma łapać:
    jedenaście cyfr z poprawną sumą gdziekolwiek albo z błędną sumą zaraz po słowie „PESEL”,
    a etykieta i reszta zdania zostają.

    Wyłapuje PESEL, który przechodzi przez anonimizację do modelu zewnętrznego, i zamianę, która
    zabiera etykietę albo sąsiednie słowa."""
    assert replaced_by(variant, text) == expected


@pytest.mark.parametrize(("variant", "text"), KEPT)
def test_a_pesel_variant_leaves_lookalikes(variant: Variant, text: str) -> None:
    """Sprawdza, czy warianty wzorca PESEL zostawiają liczby, które tylko wyglądają na PESEL:
    jedenaście cyfr z błędną sumą bez etykiety i jedenaście cyfr wewnątrz dłuższego ciągu.
    Wariant po etykiecie zostawia też numer z poprawną sumą, bo ten łapie wariant z sumą.

    Wyłapuje wzorzec, który zamienia identyfikatory z rejestru i numery przesyłek: wiedza
    z wątku znika, choć danej osobowej w niej nie ma."""
    assert replaced_by(variant, text) == text
