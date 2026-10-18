import pytest

from anonymizer_app.patterns.bank_account import find_account_by_checksum
from tests._helpers.patterns import replaced_by

# Tekst, który wariant zamienia, i wynik zamiany.
REPLACED = [
    pytest.param("PL30 1160 2202 0000 0003 1245 8701", "{KONTO}", id="pl-ze-spacjami"),
    pytest.param("PL30116022020000000312458701", "{KONTO}", id="pl-bez-spacji"),
    pytest.param("92 1020 1026 0000 1502 0345 6789", "{KONTO}", id="bez-pl-ze-spacjami"),
    pytest.param("92102010260000150203456789", "{KONTO}", id="bez-pl-bez-spacji"),
    pytest.param("PL30 1160 22020000 0003 12458701", "{KONTO}", id="spacje-mieszane"),
    pytest.param(
        "92\xa01020\xa01026\xa00000\xa01502\xa00345\xa06789",
        "{KONTO}",
        id="twarde-spacje",
    ),
    pytest.param(
        "na rachunek 92 1020 1026 0000 1502 0345 6789.",
        "na rachunek {KONTO}.",
        id="w-zdaniu",
    ),
]

# Tekst, który wariant ma zostawić bez zmian.
KEPT = [
    pytest.param("92 1020 1026 0000 1502 0345 6788", id="bledna-suma"),
    pytest.param("9210201026000015020345678", id="25-cyfr"),
    pytest.param("XPL30116022020000000312458701", id="sklejony-z-litera"),
]


@pytest.mark.parametrize(("text", "expected"), REPLACED)
def test_the_account_variant_replaces_every_notation(text: str, expected: str) -> None:
    """Sprawdza, czy wzorzec konta zamienia na znacznik numer z poprawną sumą IBAN w każdym
    zapisie: z „PL” i bez, ze spacjami co cztery cyfry, bez nich, mieszanymi i twardymi.

    Wyłapuje zapis numeru konta, który przechodzi przez anonimizację do modelu zewnętrznego,
    i „PL”, które zostaje w tekście obok znacznika."""
    assert replaced_by(find_account_by_checksum, text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_the_account_variant_leaves_lookalikes(text: str) -> None:
    """Sprawdza, czy wzorzec konta zostawia 26 cyfr z błędną sumą, 25 cyfr i numer sklejony
    z literą przed „PL”.

    Wyłapuje wzorzec, który zamienia długie identyfikatory w kształcie konta: wiedza z wątku
    znika, choć danej w niej nie ma."""
    assert replaced_by(find_account_by_checksum, text) == text
