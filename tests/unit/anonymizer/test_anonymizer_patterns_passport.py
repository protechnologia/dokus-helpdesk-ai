import pytest

from anonymizer_app.patterns.passport import find_passport_by_check_digit
from tests._helpers.patterns import replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param("EA0417295", "{PASZPORT}", id="sam-numer"),
    pytest.param(
        "legitymował się paszportem nr EA0417295.",
        "legitymował się paszportem nr {PASZPORT}.",
        id="w-zdaniu",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param("AB1234567", id="zla-cyfra-kontrolna"),
    pytest.param("XEA0417295", id="sklejony-z-litera"),
    pytest.param("EA04172950", id="dalsza-cyfra"),
    pytest.param("CBF248213", id="dowod"),
]


@pytest.mark.parametrize(("text", "expected"), REPLACED)
def test_the_passport_variant_replaces_the_number(text: str, expected: str) -> None:
    """Sprawdza, czy wzorzec paszportu zamienia na znacznik `{PASZPORT}` dwie litery i siedem
    cyfr z poprawną cyfrą kontrolną, także w zdaniu.

    Wyłapuje numer paszportu, który przechodzi przez anonimizację do modelu zewnętrznego."""
    assert replaced_by(find_passport_by_check_digit, text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_the_passport_variant_leaves_lookalikes(text: str) -> None:
    """Sprawdza, czy wzorzec paszportu zostawia kod tego kształtu z błędną cyfrą kontrolną,
    numer sklejony z literą albo cyfrą i numer dowodu osobistego.

    Wyłapuje wzorzec, który zamienia kody w kształcie paszportu: wiedza z wątku znika, choć
    danej w niej nie ma."""
    assert replaced_by(find_passport_by_check_digit, text) == text
