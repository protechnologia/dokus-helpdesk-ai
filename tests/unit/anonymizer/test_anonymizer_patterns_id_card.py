import pytest

from anonymizer_app.patterns.id_card import find_id_card_by_check_digit
from tests._helpers.patterns import replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param("CBF248213", "{DOWÓD}", id="sam-numer"),
    pytest.param(
        "skan dowodu osobistego CBF248213, a",
        "skan dowodu osobistego {DOWÓD}, a",
        id="w-zdaniu",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param("ABC123456", id="zla-cyfra-kontrolna"),
    pytest.param("XCBF248213", id="sklejony-z-litera"),
    pytest.param("CBF2482130", id="dalsza-cyfra"),
    pytest.param("cbf248213", id="male-litery"),
    pytest.param("EA0417295", id="paszport"),
]


@pytest.mark.parametrize(("text", "expected"), REPLACED)
def test_the_id_card_variant_replaces_the_number(text: str, expected: str) -> None:
    """Sprawdza, czy wzorzec dowodu osobistego zamienia na znacznik `{DOWÓD}` trzy litery i sześć
    cyfr z poprawną cyfrą kontrolną, także w zdaniu.

    Wyłapuje numer dowodu, który przechodzi przez anonimizację do modelu zewnętrznego, na
    przykład po pomyleniu wartości liter w sumie."""
    assert replaced_by(find_id_card_by_check_digit, text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_the_id_card_variant_leaves_lookalikes(text: str) -> None:
    """Sprawdza, czy wzorzec dowodu zostawia kod tego kształtu z błędną cyfrą kontrolną, numer
    sklejony z literą albo cyfrą, zapis małymi literami i numer paszportu.

    Wyłapuje wzorzec, który zamienia kody produktów i spraw w kształcie dowodu: wiedza z wątku
    znika, choć danej w niej nie ma."""
    assert replaced_by(find_id_card_by_check_digit, text) == text
